"""Fetch candidate landfill polygons from OSM Overpass for human review.

Usage: python -m pipeline.sites.overpass  -> writes cache/osm/candidates_<city>.geojson
A human then copies approved polygons into config/sites.yaml (approved: true).
"""
from __future__ import annotations

import json
import time

import requests
from shapely.geometry import Polygon, mapping

from pipeline.common.config import CACHE_DIR, USER_AGENT
from pipeline.common.geo import to_metric, utm_epsg

OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

CITY_BBOX = {  # south, west, north, east (Overpass order) — search areas only
    "delhi": (28.40, 76.85, 28.90, 77.40),
    "kochi": (9.90, 76.25, 10.10, 76.45),
    "mumbai": (18.95, 72.80, 19.25, 73.00),
    "bengaluru": (12.80, 77.40, 13.20, 77.80),
    "hyderabad": (17.30, 78.30, 17.60, 78.65),
}


def query(bbox: tuple[float, float, float, float]) -> dict:
    s, w, n, e = bbox
    q = f"[out:json][timeout:90];(way[landuse=landfill]({s},{w},{n},{e});relation[landuse=landfill]({s},{w},{n},{e}););out geom tags;"
    return post(q)


def post(q: str) -> dict:
    """POST an Overpass QL query, trying mirrors with backoff."""
    last = None
    for attempt in range(3):
        for url in OVERPASS:
            try:
                r = requests.post(url, data={"data": q}, headers={"User-Agent": USER_AGENT}, timeout=180)
                if r.status_code == 200:
                    return r.json()
                last = f"{url}: HTTP {r.status_code}"
            except requests.RequestException as e:  # network error, try next mirror
                last = f"{url}: {e}"
        time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Overpass failed: {last}")


def way_polygon(el: dict) -> Polygon | None:
    pts = [(p["lon"], p["lat"]) for p in el.get("geometry", [])]
    if len(pts) < 4:
        return None
    poly = Polygon(pts)
    return poly if poly.is_valid else poly.buffer(0)


def relation_polygon(el: dict) -> Polygon | None:
    outers = []
    for m in el.get("members", []):
        if m.get("role") == "outer" and m.get("geometry"):
            pts = [(p["lon"], p["lat"]) for p in m["geometry"]]
            if len(pts) >= 4 and pts[0] == pts[-1]:
                outers.append(Polygon(pts))
    if not outers:
        return None
    from shapely.ops import unary_union

    return unary_union(outers)


def candidates(city: str) -> list[dict]:
    data = query(CITY_BBOX[city])
    out = []
    for el in data["elements"]:
        poly = way_polygon(el) if el["type"] == "way" else relation_polygon(el)
        if poly is None or poly.is_empty:
            continue
        c = poly.centroid
        area_ha = to_metric(poly, utm_epsg(c.x, c.y)).area / 1e4
        out.append(
            {
                "type": "Feature",
                "properties": {
                    "osm": f"{el['type']}/{el['id']}",
                    "name": el.get("tags", {}).get("name"),
                    "area_ha": round(area_ha, 1),
                    "centroid": [round(c.x, 5), round(c.y, 5)],
                },
                "geometry": mapping(poly),
            }
        )
    out.sort(key=lambda f: -f["properties"]["area_ha"])
    return out


def main() -> None:
    d = CACHE_DIR / "osm"
    d.mkdir(parents=True, exist_ok=True)
    for city in CITY_BBOX:
        feats = candidates(city)
        (d / f"candidates_{city}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
        print(f"== {city}: {len(feats)} candidates")
        for f in feats[:12]:
            p = f["properties"]
            print(f"  {p['osm']:<20} {p['area_ha']:>7} ha  {p['centroid']}  {p['name']}")
        time.sleep(2)


if __name__ == "__main__":
    main()
