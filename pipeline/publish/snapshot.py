"""Assemble the versioned snapshot consumed by the web app and the API.

Inputs: cache/derived/{detections,fire_days,episodes,validation,backfill_meta}.json, context, landmarks, wind.
Output: web/public/data/snapshot.json (+ cache/public/<run_id>.json)
Usage: python -m pipeline.publish.snapshot
"""
from __future__ import annotations

import json
import math
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from pipeline.briefs.template import template_brief
from pipeline.common import store
from pipeline.common.config import ROOT, load
from pipeline.common.models import Snapshot
from pipeline.common.sites import load_sites
from pipeline.context.context import build_context
from pipeline.downwind.downwind import params as dw_params
from pipeline.downwind.downwind import sector_geojson, smoke_days, window_hours
from pipeline.wind.openmeteo import wind_for_fire_days

WEB_DATA = ROOT / "web" / "public" / "data"

SOURCES = [
    {"id": "firms", "name": "NASA FIRMS VIIRS 375 m active fire (SNPP, NOAA-20; SP archive + NRT)", "url": "https://firms.modaps.eosdis.nasa.gov/", "licence": "NASA open data", "attribution": "We acknowledge the use of data and imagery from NASA's Fire Information for Resource Management System (FIRMS), part of NASA's Earth Science Data and Information System (ESDIS).", "used_for": "Detections, fire days, episodes"},
    {"id": "openmeteo", "name": "Open-Meteo Historical Weather API (ECMWF IFS 9 km; ERA5-Land; ERA5) and Forecast API", "url": "https://open-meteo.com/", "licence": "CC BY 4.0", "attribution": "Weather data by Open-Meteo.com (CC BY 4.0); ERA5/ERA5-Land: Copernicus Climate Change Service; ECMWF IFS.", "used_for": "Hourly 10 m wind for downwind modelling"},
    {"id": "osm", "name": "OpenStreetMap via Overpass API", "url": "https://www.openstreetmap.org/copyright", "licence": "ODbL 1.0", "attribution": "(c) OpenStreetMap contributors", "used_for": "Site boundaries, buildings, schools, hospitals, stations"},
    {"id": "worldpop", "name": "WorldPop Global 100 m population, 2020 (unconstrained)", "url": "https://www.worldpop.org/", "licence": "CC BY 4.0", "attribution": "WorldPop (www.worldpop.org), University of Southampton. Global High Resolution Population Denominators Project, 2020.", "used_for": "Estimated people within 1 km and 3 km"},
    {"id": "cop-dem", "name": "Copernicus DEM GLO-30 (AWS Open Data)", "url": "https://registry.opendata.aws/copernicus-dem/", "licence": "Copernicus DEM licence (free, attribution)", "attribution": "Produced using Copernicus WorldDEM-30 (c) DLR e.V. 2010-2014 and (c) Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.", "used_for": "3D terrain and contour lines"},
    {"id": "s2", "name": "Sentinel-2 L2A (AWS Open Data, Earth Search STAC)", "url": "https://registry.opendata.aws/sentinel-2-l2a-cogs/", "licence": "Copernicus Sentinel data terms (free, attribution)", "attribution": "Contains modified Copernicus Sentinel data", "used_for": "Terrain drape, Burn Scan"},
    {"id": "news", "name": "Compiled news reports (data/news_fires.csv)", "url": "https://github.com/", "licence": "Links only; quotes are short excerpts", "attribution": "Each row links to its outlet", "used_for": "Validation reference (COMPILED), not ground truth"},
]


def _ts_utc(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)


def site_stats(site_id: str, dets: list[dict], fds: list[dict], first: str, through: str) -> dict:
    sd = [d for d in dets if d["site_id"] == site_id]
    sf = [f for f in fds if f["site_id"] == site_id]
    counted = [d for d in sd if d["counted"]]
    frps = [d["frp_mw"] for d in counted if d["frp_mw"] is not None]
    cut = (date.fromisoformat(through) - timedelta(days=364)).isoformat()
    by_year = Counter(f["date_ist"][:4] for f in sf)
    years = range(int(first[:4]), int(through[:4]) + 1)
    return {
        "fire_days_by_year": {str(y): by_year.get(str(y), 0) for y in years},
        "fire_days_365": sum(f["date_ist"] >= cut for f in sf),
        "detections_counted": len(counted),
        "detections_by_tier": {t: sum(d["tier"] == t for d in sd) for t in "ABC"},
        "low_conf_ab": sum(d["low_conf_ab"] for d in sd),
        "max_frp_mw": max(frps) if frps else None,
        "last_detection_utc": max((d["ts_utc"] for d in counted), default=None),
        "first_data_date": first,
        "data_through": through,
    }


def rank_sites(sites: list[dict]) -> None:
    cfg = load("ranking")
    formula = "score = fire_days_last_365 x log10(1 + people_1km_est)"
    scored = []
    for s in sites:
        fd = s["stats"]["fire_days_365"]
        ppl = (s.get("context") or {}).get("people_1km_est")
        if fd == 0:
            s["rank"] = {"score": None, "position": None, "label": "no detections", "formula": formula}
        elif ppl is None:
            s["rank"] = {"score": None, "position": None, "label": "no population estimate", "formula": formula}
        else:
            score = (fd ** cfg["w_fire"]) * (math.log10(1 + ppl) ** cfg["w_people"])
            s["rank"] = {"score": round(score, 1), "position": None, "label": "ranked", "formula": formula}
            scored.append(s)
    for i, s in enumerate(sorted(scored, key=lambda s: -s["rank"]["score"]), 1):
        s["rank"]["position"] = i


def schools_downwind(site: dict, ctx: dict, all_sites, fds_by_site, wind_by_site, year: int) -> dict:
    schools = [s for s in ctx["schools"]]
    any_days = 0
    total = 0
    for sc in schools:
        r = smoke_days(sc["lon"], sc["lat"], [site], fds_by_site, wind_by_site, year=year)
        if r["smoke_days"]:
            any_days += 1
            total += r["smoke_days"]
    return {"year": year, "schools_considered": len(schools), "schools_downwind_any_day": any_days, "school_downwind_days": total}


def build(run_id: str | None = None) -> dict:
    t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    stages = []

    def stage(name, started, count=None):
        stages.append({"name": name, "started_at": started, "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "SUCCEEDED", "count": count})

    dets = store.get_json("derived/detections.json")
    fds = store.get_json("derived/fire_days.json")
    eps = store.get_json("derived/episodes.json")
    val = store.get_json("derived/validation.json")
    meta = store.get_json("derived/backfill_meta.json")
    sites = load_sites()
    ids = {s["site_id"] for s in sites}
    dets = [x for x in dets if x["site_id"] in ids]
    fds = [x for x in fds if x["site_id"] in ids]
    eps = [x for x in eps if x["site_id"] in ids]
    first = load("firms")["start_date"]
    through = max(v[1] for k, v in meta["availability"].items() if k.endswith("_NRT"))
    run_id = run_id or "local-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())

    fds_by_site: dict[str, list[dict]] = defaultdict(list)
    for f in fds:
        fds_by_site[f["site_id"]].append(f)

    # Wind for every fire day
    s0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    wind_by_site: dict[str, dict[str, dict]] = {}
    for s in sites:
        rows = wind_for_fire_days(s, [f["date_ist"] for f in fds_by_site[s["site_id"]]])
        wind_by_site[s["site_id"]] = {r["ts_ist"]: r for r in rows}
    stage("FetchWind", s0, sum(len(v) for v in wind_by_site.values()))

    # Snapshot wind: only the window hours of each fire day (for receipts)
    p = dw_params()
    wind_out: dict[str, dict[str, list[dict]]] = {}
    sectors = []
    for s in sites:
        w = wind_by_site[s["site_id"]]
        per = {}
        for f in fds_by_site[s["site_id"]]:
            hours, _ = window_hours(f, p["window_hours"])
            per[f["date_ist"]] = [{k: w[h][k] for k in ("ts_ist", "ws_ms", "wd_from_deg", "model")} for h in hours if h in w]
            sec = sector_geojson(s, f, w)
            if sec:
                sectors.append({**sec["properties"], "geometry": sec["geometry"]})
        wind_out[s["site_id"]] = per

    # Context and stats
    s0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    last_full_year = date.fromisoformat(through).year - 1
    for s in sites:
        try:
            s["context"] = build_context(s)
        except Exception as e:  # noqa: BLE001 - context is optional; UI says "not available"
            print("context failed", s["site_id"], e)
            s["context"] = None
        s["stats"] = site_stats(s["site_id"], dets, fds, first, through)
        if s["context"]:
            s["schools_downwind"] = schools_downwind(s, s["context"], sites, fds_by_site, wind_by_site, last_full_year)
    rank_sites(sites)
    stage("FetchContext", s0, len(sites))

    # Landmarks: Smoke Days per year
    s0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    raw_lm = store.get("raw/landmarks.json")
    landmarks = []
    years = list(range(int(first[:4]), int(through[:4]) + 1))
    for lm in json.loads(raw_lm) if raw_lm else []:
        res = {str(y): smoke_days(lm["lon"], lm["lat"], sites, fds_by_site, wind_by_site, year=y) for y in years}
        res["all"] = smoke_days(lm["lon"], lm["lat"], sites, fds_by_site, wind_by_site, year=None)
        landmarks.append({k: lm[k] for k in ("id", "name", "kind", "city", "lon", "lat", "osm")} | {"results": res})
    stage("ComputeDownwind", s0, len(landmarks))

    # Briefs (template; Bedrock replaces these in the cloud run)
    # Bedrock briefs (cloud GenerateBriefs stage) when present, else the deterministic template
    generated = {(b["site_id"], b["lang"]): b for b in store.get_json("derived/briefs.json", []) or []}
    briefs = []
    for s in sites:
        for lang in ("en", "hi"):
            briefs.append(generated.get((s["site_id"], lang)) or template_brief(s, eps, lang, run_id))

    snap = {
        "pipeline_run_id": run_id,
        "generated_at": t0,
        "data_through": through,
        "sample": False,
        "sources": SOURCES,
        "parameters": {"attribution": load("attribution"), "downwind": p, "ranking": load("ranking"), "firms": {k: v for k, v in load("firms").items() if k != "base"}},
        "sites": sites,
        "detections": dets,
        "fire_days": fds,
        "episodes": eps,
        "wind": wind_out,
        "sectors": sectors,
        "landmarks": landmarks,
        "validation": val,
        "briefs": briefs,
        "burn_obs": _load_burn_obs(),
        "runs": [],
    }
    snap["runs"] = [{"run_id": run_id, "kind": "local", "started_at": t0, "ended_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "status": "SUCCEEDED", "stages": stages, "where": "local"}]
    Snapshot.model_validate(snap)
    return snap


def _load_burn_obs() -> list[dict]:
    raw = store.get("derived/burn_obs.json")
    return json.loads(raw) if raw else []


def main() -> None:
    snap = build()
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    body = json.dumps(snap, ensure_ascii=False, separators=(",", ":"))
    (WEB_DATA / "snapshot.json").write_text(body, encoding="utf-8")
    store.put(f"public/{snap['pipeline_run_id']}.json", body.encode(), "application/json")
    print("snapshot", snap["pipeline_run_id"], f"{len(body) / 1e6:.2f} MB", "sites", len(snap["sites"]), "dets", len(snap["detections"]), "fire days", len(snap["fire_days"]), "landmarks", len(snap["landmarks"]))


if __name__ == "__main__":
    main()
