"""Backfill FIRMS detections per city bbox (archive SP + NRT gap), attribute, write outputs.

Usage: python -m pipeline.firms.backfill [--cities delhi] [--start 2019-01-01]
Writes cache/derived/detections.json, fire_days.json, episodes.json
"""
from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta

from shapely.geometry import shape
from shapely.ops import unary_union

import yaml

from pipeline.attribute.attribute import attribute, episodes, fire_days
from pipeline.common import store
from pipeline.common.config import CONFIG_DIR, load
from pipeline.common.geo import to_metric, to_wgs84
from pipeline.common.sites import load_sites
from pipeline.firms.client import Firms, dedupe

log = logging.getLogger("backfill")


def city_bbox(sites: list[dict], buffer_km: float) -> tuple[float, float, float, float]:
    """Union of site polygons buffered by buffer_km (plus Tier C radius), as west,south,east,north."""
    epsg = sites[0]["utm_epsg"]
    extra = load("attribution")["tier_c_radius_m"]
    u = unary_union([to_metric(shape(s["polygon"]), epsg).buffer(buffer_km * 1000 + extra) for s in sites])
    w, s, e, n = to_wgs84(u, epsg).bounds
    return (round(w, 4), round(s, 4), round(e, 4), round(n, 4))


def plan(cities: dict, avail: dict, start: date, today: date) -> list[tuple]:
    cfg = load("firms")
    jobs = []
    for city, bbox in cities.items():
        for src in cfg["archive_sources"]:
            lo, hi = avail[src]
            s = max(start, lo)
            jobs.append((src, city, bbox, s, hi, hi))
        sp_end = min(avail[s][1] for s in cfg["archive_sources"])
        for src in cfg["nrt_sources"]:
            lo, hi = avail[src]
            s = max(sp_end + timedelta(days=1), lo)
            # NRT windows older than 7 days are stable; cache them.
            jobs.append((src, city, bbox, s, min(hi, today), today - timedelta(days=7)))
    return jobs


def run(city_filter: list[str] | None = None, start: str | None = None) -> dict:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    cfg = load("firms")
    sites = [s for s in load_sites() if not city_filter or s["city"] in city_filter]
    by_city: dict[str, list[dict]] = {}
    for s in sites:
        by_city.setdefault(s["city"], []).append(s)
    # The raw FIRMS cache is keyed by source/city/window, so a city's bbox is frozen once used
    # (config/city_bboxes.yaml). Delete an entry to re-fetch that city with a new bbox.
    frozen_p = CONFIG_DIR / "city_bboxes.yaml"
    frozen = (yaml.safe_load(frozen_p.read_text()) or {}) if frozen_p.exists() else {}
    cities = {c: tuple(frozen[c]) if c in frozen else city_bbox(ss, cfg["city_buffer_km"]) for c, ss in by_city.items()}
    if any(c not in frozen for c in cities):
        frozen.update({c: list(b) for c, b in cities.items()})
        frozen_p.write_text("# W,S,E,N per city; frozen because raw FIRMS cache keys do not include the bbox" + chr(10) + yaml.safe_dump(frozen, default_flow_style=True))
    firms = Firms()
    avail = firms.availability()
    today = date.today()
    jobs = plan(cities, avail, date.fromisoformat(start or cfg["start_date"]), today)
    est = sum(((hi - lo).days // cfg["window_days"] + 1) for _, _, _, lo, hi, _ in jobs)
    log.info("cities=%s bboxes=%s estimated FIRMS requests (uncached)=%d", list(cities), cities, est)
    raw = []
    for src, city, bbox, lo, hi, cache_until in jobs:
        got = firms.fetch_range(src, city, bbox, lo, hi, cache_until=cache_until)
        log.info("%s %s %s..%s: %d rows", src, city, lo, hi, len(got))
        raw.extend(got)
    raw = dedupe(raw)
    dets = attribute(raw, sites)
    fds = fire_days(dets)
    eps = episodes(fds)
    store.put_json("derived/detections.json", dets)
    store.put_json("derived/fire_days.json", fds)
    store.put_json("derived/episodes.json", eps)
    meta = {
        "cities": cities,
        "availability": {k: [v[0].isoformat(), v[1].isoformat()] for k, v in avail.items() if k in cfg["archive_sources"] + cfg["nrt_sources"]},
        "requests_made": firms.requests_made,
        "estimated_requests": est,
        "raw_rows_deduped": len(raw),
        "attributed": len(dets),
    }
    store.put_json("derived/backfill_meta.json", meta, indent=1)
    log.info("raw=%d attributed=%d fire_days=%d episodes=%d requests=%d", len(raw), len(dets), len(fds), len(eps), firms.requests_made)
    return meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cities", nargs="*")
    ap.add_argument("--start")
    a = ap.parse_args()
    run(a.cities, a.start)
