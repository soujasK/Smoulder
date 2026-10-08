"""Neighbourhood context per site: OSM-mapped buildings, schools, hospitals (COUNTED) and
WorldPop 2020 population (ESTIMATED) within 1 km and 3 km of the polygon edge.

Rings are the polygon buffered by 1 km / 3 km (they include the site itself).
Usage: python -m pipeline.context.context [site_id ...]
"""
from __future__ import annotations

import json
import sys
import time

import requests
from shapely.geometry import Point, mapping, shape

from pipeline.common import store
from pipeline.common.config import USER_AGENT
from pipeline.common.geo import project_point, to_metric, to_wgs84
from pipeline.common.sites import load_sites
from pipeline.sites.overpass import post

WORLDPOP = "https://api.worldpop.org/v1/services/stats"
WORLDPOP_TASK = "https://api.worldpop.org/v1/tasks/"
RINGS_M = (1000, 3000)


def ring(site: dict, metres: float):
    return to_wgs84(to_metric(shape(site["polygon"]), site["utm_epsg"]).buffer(metres, quad_segs=8), site["utm_epsg"])


def poly_filter(geom) -> str:
    g = geom.simplify(0.0005)
    coords = list(g.exterior.coords)
    return " ".join(f"{lat:.5f} {lon:.5f}" for lon, lat in coords)


def osm_counts(site: dict) -> dict:
    out = {}
    for m in RINGS_M:
        pf = poly_filter(ring(site, m))
        q = (
            f'[out:json][timeout:180];'
            f'(way[building](poly:"{pf}");relation[building](poly:"{pf}"););out count;'
            f'nwr[amenity~"^(hospital|clinic)$"](poly:"{pf}");out count;'
        )
        res = post(q)
        counts = [int(e["tags"]["total"]) for e in res["elements"] if e["type"] == "count"]
        out[f"buildings_{m // 1000}km"] = counts[0]
        out[f"hospitals_{m // 1000}km"] = counts[1]
        time.sleep(2)
    return out


def osm_schools(site: dict, metres: float) -> list[dict]:
    pf = poly_filter(ring(site, metres))
    q = f'[out:json][timeout:180];nwr[amenity~"^(school|college|kindergarten)$"](poly:"{pf}");out center tags;'
    res = post(q)
    out = []
    for e in res["elements"]:
        c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        if c.get("lat") is None:
            continue
        out.append({"osm": f"{e['type']}/{e['id']}", "name": e.get("tags", {}).get("name"), "amenity": e["tags"].get("amenity"), "lon": round(c["lon"], 5), "lat": round(c["lat"], 5)})
    return out


def worldpop(geom, year: int = 2020) -> float:
    for attempt in range(5):
        try:
            return _worldpop(geom, year)
        except (requests.RequestException, TimeoutError) as e:
            if attempt == 4:
                raise
            print("worldpop retry", e)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def _worldpop(geom, year: int) -> float:
    fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(geom.simplify(0.0003))}]}
    r = requests.get(WORLDPOP, params={"dataset": "wpgppop", "year": year, "geojson": json.dumps(fc)}, headers={"User-Agent": USER_AGENT}, timeout=60)
    r.raise_for_status()
    j = r.json()
    if j.get("error"):
        raise RuntimeError(j)
    task = j["taskid"]
    for _ in range(60):
        t = requests.get(WORLDPOP_TASK + task, headers={"User-Agent": USER_AGENT}, timeout=60).json()
        if t["status"] == "finished":
            if t.get("error"):
                raise RuntimeError(t)
            return float(t["data"]["total_population"])
        time.sleep(2)
    raise TimeoutError("WorldPop task timed out")


def build_context(site: dict) -> dict:
    key = f"raw/context/{site['site_id']}.json"
    hit = store.get(key)
    if hit:
        return json.loads(hit)
    ctx = {"site_id": site["site_id"], **osm_counts(site)}
    schools = osm_schools(site, 3000)
    poly_m = to_metric(shape(site["polygon"]), site["utm_epsg"])
    for s in schools:
        s["distance_m"] = round(poly_m.distance(Point(project_point(s["lon"], s["lat"], site["utm_epsg"]))))
    schools.sort(key=lambda s: s["distance_m"])
    ctx["schools_1km"] = sum(s["distance_m"] <= 1000 for s in schools)
    ctx["schools_3km"] = len(schools)
    ctx["nearest_school_m"] = schools[0]["distance_m"] if schools else None
    ctx["schools"] = schools
    for m in RINGS_M:
        ctx[f"people_{m // 1000}km_est"] = round(worldpop(ring(site, m)))
    ctx["sources"] = {
        "osm": "(c) OpenStreetMap contributors, ODbL. Counts are OSM-mapped features, not a census.",
        "population": "WorldPop 2020, Global per-country 100 m unconstrained (wpgppop), CC BY 4.0, via api.worldpop.org stats service.",
    }
    ctx["retrieved_on"] = time.strftime("%Y-%m-%d")
    store.put(key, json.dumps(ctx).encode(), "application/json")
    return ctx


def main(ids: list[str]) -> None:
    for s in load_sites():
        if ids and s["site_id"] not in ids:
            continue
        c = build_context(s)
        print(s["site_id"], {k: v for k, v in c.items() if k not in ("schools", "sources")})


if __name__ == "__main__":
    main(sys.argv[1:])
