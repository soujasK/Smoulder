"""Public landmarks (metro/rail stations) near each site, for offline Smoke Days and Demo Mode.

Never private homes: only OSM railway=station / public_transport=station features with a name.
Usage: python -m pipeline.sites.landmarks -> cache/raw/landmarks.json
"""
from __future__ import annotations

import json
import math

from shapely.geometry import Point, shape

from pipeline.common import store
from pipeline.common.geo import project_point, to_metric
from pipeline.common.sites import load_sites
from pipeline.sites.overpass import post

PER_SITE = 4
RADIUS_M = 4000


def fetch(site: dict) -> list[dict]:
    lon, lat = site["centroid"]
    dlat = (RADIUS_M + 1500) / 111000
    dlon = dlat / max(0.2, math.cos(math.radians(lat)))
    q = f'[out:json][timeout:60];node[railway=station][name]({lat - dlat},{lon - dlon},{lat + dlat},{lon + dlon});out;'
    res = post(q)
    poly = to_metric(shape(site["polygon"]), site["utm_epsg"])
    out = []
    for e in res["elements"]:
        c = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        t = e.get("tags", {})
        name = t.get("name:en") or t.get("name")
        if c.get("lat") is None or not name:
            continue
        d = poly.distance(Point(project_point(c["lon"], c["lat"], site["utm_epsg"])))
        if d > RADIUS_M:
            continue
        kind = "metro station" if t.get("station") in ("subway", "light_rail") or "metro" in (t.get("network", "") + t.get("operator", "")).lower() else "railway station"
        out.append(
            {
                "id": f"{site['site_id']}-{e['type'][0]}{e['id']}",
                "name": name,
                "name_hi": t.get("name:hi"),
                "kind": kind,
                "city": site["city"],
                "lon": round(c["lon"], 5),
                "lat": round(c["lat"], 5),
                "osm": f"{e['type']}/{e['id']}",
                "near": site["site_id"],
                "distance_m": round(d),
            }
        )
    # dedupe by name (stations often have several OSM objects), keep nearest
    best: dict[str, dict] = {}
    for o in sorted(out, key=lambda o: o["distance_m"]):
        best.setdefault(o["name"], o)
    return sorted(best.values(), key=lambda o: o["distance_m"])[:PER_SITE]


def fetch_nominatim(site: dict) -> list[dict]:
    """Fallback when every Overpass mirror is down: Nominatim search for stations in the same box."""
    import time

    import requests

    from pipeline.common.config import USER_AGENT

    lon, lat = site["centroid"]
    dlat = (RADIUS_M + 1500) / 111000
    dlon = dlat / max(0.2, math.cos(math.radians(lat)))
    poly = to_metric(shape(site["polygon"]), site["utm_epsg"])
    out = []
    for q in ("railway station", "metro station"):
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": q, "format": "jsonv2", "viewbox": f"{lon - dlon},{lat + dlat},{lon + dlon},{lat - dlat}", "bounded": 1, "limit": 40, "extratags": 1, "namedetails": 1},
            headers={"User-Agent": USER_AGENT}, timeout=60,
        )
        r.raise_for_status()
        time.sleep(1.1)  # Nominatim usage policy: at most 1 request per second
        for e in r.json():
            if e.get("category") not in ("railway", "public_transport") or e.get("type") not in ("station", "halt"):
                continue
            nd = e.get("namedetails") or {}
            name = nd.get("name:en") or nd.get("name") or e.get("name")
            if not name:
                continue
            elon, elat = float(e["lon"]), float(e["lat"])
            d = poly.distance(Point(project_point(elon, elat, site["utm_epsg"])))
            if d > RADIUS_M:
                continue
            xt = e.get("extratags") or {}
            kind = "metro station" if xt.get("station") in ("subway", "light_rail") or "metro" in (name + xt.get("network", "") + xt.get("operator", "")).lower() else "railway station"
            out.append({
                "id": f"{site['site_id']}-{e['osm_type'][0]}{e['osm_id']}", "name": name, "name_hi": nd.get("name:hi"), "kind": kind,
                "city": site["city"], "lon": round(elon, 5), "lat": round(elat, 5), "osm": f"{e['osm_type']}/{e['osm_id']}",
                "near": site["site_id"], "distance_m": round(d),
            })
    best: dict[str, dict] = {}
    for o in sorted(out, key=lambda o: o["distance_m"]):
        best.setdefault(o["name"], o)
    return sorted(best.values(), key=lambda o: o["distance_m"])[:PER_SITE]


def main(ids: list[str] | None = None) -> None:
    """Rebuild landmarks; with ids, keep cached landmarks for other sites and refresh only these."""
    allm = []
    if ids:
        old = store.get("raw/landmarks.json")
        allm = [m for m in json.loads(old) if m["near"] not in ids] if old else []
    for s in load_sites():
        if ids and s["site_id"] not in ids:
            continue
        try:
            got = fetch(s)
        except RuntimeError as e:  # Overpass down
            print("overpass failed, using Nominatim:", e)
            got = fetch_nominatim(s)
        print(s["site_id"], [(g["name"], g["distance_m"]) for g in got])
        allm.extend(got)
    store.put("raw/landmarks.json", json.dumps(allm, ensure_ascii=False, indent=1).encode(), "application/json")


if __name__ == "__main__":
    import sys

    main(sys.argv[1:] or None)
