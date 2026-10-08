"""Smoke Days: was a point downwind of a landfill on that landfill's fire days?  Tier: MODELLED.

For target P and site S (docs/METHOD.md §5):
  d = distance(S.polygon edge, P); skip if d > R
  b = geodesic bearing S.centroid -> P
  hours h in the window [hour of first counted detection (IST), + H hours):
      wd_to = (wd_from + 180) mod 360
      downwind(h) = ws >= ws_min and angdiff(b, wd_to) <= half_width
      calm(h)     = ws < ws_min
  Smoke Day = a fire day of any site within R with downwind hours >= min_hours.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from pyproj import Geod
from shapely.geometry import Point, Polygon, mapping, shape
from shapely.ops import unary_union

from pipeline.common.config import load
from pipeline.common.geo import ang_diff, compass, project_point, to_metric, to_wgs84

IST = timezone(timedelta(hours=5, minutes=30))
GEOD = Geod(ellps="WGS84")


def params(cfg: dict | None = None) -> dict:
    cfg = cfg or load("downwind")
    return {k: cfg[k] for k in ("radius_km", "window_hours", "ws_min_ms", "half_width_deg", "min_hours")}


def bearing(lon0: float, lat0: float, lon1: float, lat1: float) -> float:
    az, _, _ = GEOD.inv(lon0, lat0, lon1, lat1)
    return az % 360.0


def edge_distance_m(site: dict, lon: float, lat: float) -> float:
    poly = to_metric(shape(site["polygon"]), site["utm_epsg"])
    return poly.distance(Point(*project_point(lon, lat, site["utm_epsg"])))


def window_hours(fire_day: dict, H: int) -> tuple[list[str], bool]:
    """IST hour stamps ('YYYY-MM-DDTHH:00') in the window, and whether the date-only fallback was used."""
    if fire_day.get("first_ts_utc"):
        t0 = datetime.strptime(fire_day["first_ts_utc"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).astimezone(IST)
        t0 = t0.replace(minute=0, second=0, microsecond=0)
        return [(t0 + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00") for k in range(H)], False
    d = fire_day["date_ist"]
    return [f"{d}T{h:02d}:00" for h in range(24)], True


def evaluate_hours(b: float, hours: list[str], wind: dict[str, dict], p: dict) -> dict:
    down, calm, missing, models = [], 0, 0, set()
    for h in hours:
        w = wind.get(h)
        if w is None:
            missing += 1
            continue
        models.add(w["model"])
        if w["ws_ms"] < p["ws_min_ms"]:
            calm += 1
            continue
        wd_to = (w["wd_from_deg"] + 180.0) % 360.0
        if ang_diff(b, wd_to) <= p["half_width_deg"]:
            down.append(h)
    return {"downwind_hours": len(down), "downwind_at": down, "calm_hours": calm, "missing_hours": missing, "models": sorted(models)}


def smoke_days(
    lon: float,
    lat: float,
    sites: list[dict],
    fire_days_by_site: dict[str, list[dict]],
    wind_by_site: dict[str, dict[str, dict]],
    year: int | None = None,
    cfg: dict | None = None,
) -> dict:
    """Compute Smoke Days for point (lon, lat). Pure function: no I/O, nothing persisted."""
    p = params(cfg)
    R = p["radius_km"] * 1000.0
    nearby = []
    for s in sites:
        d = edge_distance_m(s, lon, lat)
        if d > R:
            continue
        b = bearing(s["centroid"][0], s["centroid"][1], lon, lat)
        fds = [f for f in fire_days_by_site.get(s["site_id"], []) if year is None or f["date_ist"].startswith(str(year))]
        nearby.append({"site_id": s["site_id"], "name": s["name"], "distance_m": round(d), "bearing_deg": round(b), "bearing_compass": compass(b), "fire_days": len(fds), "_fds": fds, "_b": b})
    nearby.sort(key=lambda n: n["distance_m"])

    per_day: dict[str, list[dict]] = defaultdict(list)
    for n in nearby:
        wind = wind_by_site.get(n["site_id"], {})
        for fd in n["_fds"]:
            hours, date_only = window_hours(fd, p["window_hours"])
            ev = evaluate_hours(n["_b"], hours, wind, p)
            per_day[fd["date_ist"]].append(
                {
                    "site_id": n["site_id"],
                    "name": n["name"],
                    "detections": fd["detections"],
                    "max_frp_mw": fd.get("max_frp_mw"),
                    "window_start_ist": hours[0],
                    "date_only_fallback": date_only,
                    **ev,
                }
            )

    days, calm_days, no_wind_days = [], [], []
    for d, entries in sorted(per_day.items()):
        smoke = [e for e in entries if e["downwind_hours"] >= p["min_hours"]]
        if smoke:
            days.append({"date_ist": d, "sites": entries})
        elif any(e["calm_hours"] >= p["min_hours"] for e in entries):
            calm_days.append({"date_ist": d, "sites": entries})
        elif all(not e["models"] for e in entries):  # no wind data at all for the window
            no_wind_days.append(d)

    for n in nearby:
        n.pop("_fds")
        n.pop("_b")
    return {
        "point": [round(lon, 3), round(lat, 3)],
        "year": year,
        "smoke_days": len(days),
        "days": days,
        "calm_days": len(calm_days),
        "calm": calm_days,
        "fire_days_nearby": len(per_day),
        "no_wind_days": no_wind_days,
        "nearest_sites": nearby,
        "parameters": p,
        "tier": "MODELLED",
    }


def sector_geojson(site: dict, fire_day: dict, wind: dict[str, dict], cfg: dict | None = None) -> dict | None:
    """Union of hourly downwind wedges (radius R) for one site and fire day, as a GeoJSON Feature."""
    p = params(cfg)
    hours, date_only = window_hours(fire_day, p["window_hours"])
    epsg = site["utm_epsg"]
    cx, cy = project_point(site["centroid"][0], site["centroid"][1], epsg)
    R = p["radius_km"] * 1000.0
    wedges, dirs = [], []
    for h in hours:
        w = wind.get(h)
        if not w or w["ws_ms"] < p["ws_min_ms"]:
            continue
        to = (w["wd_from_deg"] + 180.0) % 360.0
        dirs.append(round(to))
        wedges.append(_wedge(cx, cy, R, to, p["half_width_deg"]))
    if not wedges:
        return None
    u = to_wgs84(unary_union(wedges), epsg).simplify(0.0003)
    return {
        "type": "Feature",
        "properties": {"site_id": site["site_id"], "date_ist": fire_day["date_ist"], "wind_to_deg": dirs, "date_only_fallback": date_only, "radius_km": p["radius_km"]},
        "geometry": mapping(u),
    }


def _wedge(cx: float, cy: float, R: float, to_deg: float, half: float, steps: int = 12) -> Polygon:
    import math

    pts = [(cx, cy)]
    for i in range(steps + 1):
        a = math.radians(to_deg - half + 2 * half * i / steps)
        pts.append((cx + R * math.sin(a), cy + R * math.cos(a)))
    pts.append((cx, cy))
    return Polygon(pts)
