from datetime import datetime, timezone

from conftest import CX, CY, EPSG, square_site

from pipeline.attribute.attribute import attribute, episodes, fire_days
from pipeline.common.geo import unproject_point
from pipeline.firms.client import RawDetection

CFG = {"tier_c_radius_m": 2000, "fallback_scan_km": 0.375, "fallback_track_km": 0.375, "count_low_confidence": False, "gap_days": 1}


def det(dx, dy, conf="n", scan=0.4, track=0.4, ts="2024-04-21T08:00"):
    lon, lat = unproject_point(CX + dx, CY + dy, EPSG)
    return RawDetection(lat, lon, datetime.fromisoformat(ts).replace(tzinfo=timezone.utc), "VIIRS_SNPP_SP", "N", "VIIRS", conf, 5.0, scan, track, "D", 330.0, "0")


def tiers(dets, cfg=CFG):
    return [(d["tier"], d["counted"]) for d in attribute(dets, [square_site()], cfg)]


def test_tier_a_inside():
    assert tiers([det(0, 0)]) == [("A", True)]
    assert tiers([det(499, 0)]) == [("A", True)]


def test_tier_b_footprint_intersects():
    # centre 150 m outside the edge; 400 m footprint has half-width 200 m, reaches in
    assert tiers([det(650, 0)]) == [("B", True)]


def test_tier_c_boundary_not_counted():
    # centre 250 m outside: half-width 200 m does not reach -> C, never counted
    assert tiers([det(750, 0)]) == [("C", False)]
    assert tiers([det(2450, 0, scan=0.1, track=0.1)]) == [("C", False)]  # 1950 m from edge
    assert tiers([det(2550, 0, scan=0.1, track=0.1)]) == []  # 2050 m: dropped


def test_fallback_footprint_flagged():
    out = attribute([det(650, 0, scan=None, track=None)], [square_site()], CFG)
    assert out[0]["fallback_footprint"] is True
    assert out[0]["tier"] == "B"  # 375 m footprint, half 187.5 m reaches 150 m


def test_low_confidence_excluded_by_default():
    out = attribute([det(0, 0, conf="l")], [square_site()], CFG)
    assert out[0]["tier"] == "A" and out[0]["counted"] is False and out[0]["low_conf_ab"] is True
    assert fire_days(out) == []
    assert attribute([det(0, 0, conf="l")], [square_site()], dict(CFG, count_low_confidence=True))[0]["counted"] is True


def test_nearest_site_wins():
    a, b = square_site("a"), square_site("b", half_m=100)
    out = attribute([det(0, 0)], [a, b], CFG)
    assert len(out) == 1 and out[0]["tier"] == "A"


def test_fire_days_and_episode_gap_rule():
    ds = [det(0, 0, ts=t) for t in ["2024-04-01T08:00", "2024-04-02T08:00", "2024-04-04T08:00", "2024-04-07T08:00"]]
    ds.append(det(750, 0, ts="2024-04-10T08:00"))  # tier C: not a fire day
    fds = fire_days(attribute(ds, [square_site()], CFG))
    assert [f["date_ist"] for f in fds] == ["2024-04-01", "2024-04-02", "2024-04-04", "2024-04-07"]
    eps = episodes(fds, gap_days=1)
    assert [(e["start_date"], e["end_date"], e["fire_days"]) for e in eps] == [("2024-04-01", "2024-04-04", 3), ("2024-04-07", "2024-04-07", 1)]
    assert len(episodes(fds, gap_days=0)) == 3
