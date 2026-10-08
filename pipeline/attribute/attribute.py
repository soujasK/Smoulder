"""Attribute FIRMS detections to landfill polygons; derive fire days and episodes.

Tier A: pixel centre inside the polygon.
Tier B: pixel footprint (scan x track) intersects the polygon, centre outside.
Tier C: within tier_c_radius_m of the polygon, no intersection. Shown, never counted.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from shapely.geometry import Point, shape

from pipeline.common.config import load
from pipeline.common.geo import footprint, project_point, to_metric
from pipeline.firms.client import RawDetection


class SiteGeom:
    def __init__(self, site: dict):
        self.site_id = site["site_id"]
        self.epsg = site["utm_epsg"]
        self.poly_m = to_metric(shape(site["polygon"]), self.epsg)


def classify(det: RawDetection, sg: SiteGeom, cfg: dict) -> tuple[str | None, float, bool]:
    """Return (tier or None, distance in metres from pixel centre to polygon, fallback_footprint)."""
    x, y = project_point(det.lon, det.lat, sg.epsg)
    p = Point(x, y)
    dist = sg.poly_m.distance(p)
    fallback = det.scan_km is None or det.track_km is None
    scan = cfg["fallback_scan_km"] if det.scan_km is None else det.scan_km
    track = cfg["fallback_track_km"] if det.track_km is None else det.track_km
    if dist == 0.0:
        return "A", 0.0, fallback
    if footprint(x, y, scan, track).intersects(sg.poly_m):
        return "B", dist, fallback
    if dist <= cfg["tier_c_radius_m"]:
        return "C", dist, fallback
    return None, dist, fallback


def is_counted(tier: str, confidence: str, cfg: dict, fire_type: str | None = None) -> bool:
    if tier not in ("A", "B"):
        return False
    if confidence.lower() in ("l", "low") and not cfg["count_low_confidence"]:
        return False
    # FIRMS type 2 = "other static land source": NASA's flag for persistent heat (industry, plants), not a fire event
    if fire_type == "2" and not cfg.get("count_static_sources", False):
        return False
    return True


def attribute(dets: list[RawDetection], sites: list[dict], cfg: dict | None = None) -> list[dict]:
    """Assign each detection to at most one site (best tier, then nearest)."""
    cfg = cfg or load("attribution")
    geoms = [SiteGeom(s) for s in sites]
    rank = {"A": 0, "B": 1, "C": 2}
    out = []
    for d in dets:
        best = None
        for sg in geoms:
            tier, dist, fb = classify(d, sg, cfg)
            if tier is None:
                continue
            cand = (rank[tier], dist, sg.site_id, tier, fb)
            if best is None or cand < best:
                best = cand
        if best is None:
            continue
        _, dist, site_id, tier, fb = best
        conf = d.confidence.lower()
        out.append(
            {
                "site_id": site_id,
                "det_id": d.det_id,
                "ts_utc": d.ts_utc.strftime("%Y-%m-%dT%H:%MZ"),
                "date_ist": d.date_ist,
                "source": d.source,
                "satellite": d.satellite,
                "confidence": conf,
                "frp_mw": d.frp_mw,
                "scan_km": d.scan_km,
                "track_km": d.track_km,
                "lat": round(d.lat, 5),
                "lon": round(d.lon, 5),
                "daynight": d.daynight,
                "tier": tier,
                "dist_m": round(dist, 1),
                "fallback_footprint": fb,
                "counted": is_counted(tier, conf, cfg, d.type),
                "low_conf_ab": tier in ("A", "B") and conf in ("l", "low"),
            }
        )
    return out


def fire_days(dets: list[dict]) -> list[dict]:
    """Per site: IST dates with at least one counted detection."""
    by = defaultdict(list)
    for d in dets:
        by[(d["site_id"], d["date_ist"])].append(d)
    out = []
    for (site_id, day), ds in sorted(by.items()):
        counted = [d for d in ds if d["counted"]]
        if not counted:
            continue
        frps = [d["frp_mw"] for d in counted if d["frp_mw"] is not None]
        out.append(
            {
                "site_id": site_id,
                "date_ist": day,
                "detections": len(counted),
                "tier_a": sum(d["tier"] == "A" for d in counted),
                "tier_b": sum(d["tier"] == "B" for d in counted),
                "low_conf_ab": sum(d["low_conf_ab"] for d in ds),
                "max_frp_mw": max(frps) if frps else None,
                "first_ts_utc": min(d["ts_utc"] for d in counted),
                "satellites": sorted({d["satellite"] for d in counted}),
            }
        )
    return out


def episodes(fdays: list[dict], gap_days: int | None = None) -> list[dict]:
    """Runs of fire days where consecutive days are at most gap_days+1 apart."""
    if gap_days is None:
        gap_days = load("attribution")["gap_days"]
    by = defaultdict(list)
    for f in fdays:
        by[f["site_id"]].append(f)
    out = []
    for site_id, fs in by.items():
        fs.sort(key=lambda f: f["date_ist"])
        cur: list[dict] = []
        for f in fs:
            if cur and (date.fromisoformat(f["date_ist"]) - date.fromisoformat(cur[-1]["date_ist"])) > timedelta(days=gap_days + 1):
                out.append(_episode(site_id, cur))
                cur = []
            cur.append(f)
        if cur:
            out.append(_episode(site_id, cur))
    return sorted(out, key=lambda e: (e["site_id"], e["start_date"]))


def _episode(site_id: str, fs: list[dict]) -> dict:
    frps = [f["max_frp_mw"] for f in fs if f["max_frp_mw"] is not None]
    return {
        "site_id": site_id,
        "start_date": fs[0]["date_ist"],
        "end_date": fs[-1]["date_ist"],
        "fire_days": len(fs),
        "span_days": (date.fromisoformat(fs[-1]["date_ist"]) - date.fromisoformat(fs[0]["date_ist"])).days + 1,
        "detections": sum(f["detections"] for f in fs),
        "max_frp_mw": max(frps) if frps else None,
    }
