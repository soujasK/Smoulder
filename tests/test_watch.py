from conftest import CX, CY, EPSG, square_site

from pipeline.common.geo import unproject_point
from pipeline.watch.watch import MemoryNotifier, MemoryRepo, process

P = {"radius_km": 5.0, "window_hours": 6, "ws_min_ms": 1.0, "half_width_deg": 30, "min_hours": 1}
SITE = dict(square_site("sq"), city_name="Delhi")
SITE["name"] = "Square"
DET = {"site_id": "sq", "det_id": "d1", "ts_utc": "2024-04-21T20:15Z", "satellite": "N20", "confidence": "n", "frp_mw": 3.8, "tier": "A", "counted": True}


def sub(sub_id, dy_m, mode="downwind"):
    lon, lat = unproject_point(CX, CY + dy_m, EPSG)  # north of the site
    return {"sub_id": sub_id, "lon_r": round(lon, 3), "lat_r": round(lat, 3), "mode": mode}


def wind_toward_north(site, det):
    return [{"ts_ist": f"2024-04-22T{h:02d}:00", "ws_ms": 3.0, "wd_from_deg": 180, "model": "forecast"} for h in range(2, 14)]


def run(repo, notifier, dets=None, replay_of=None):
    return process(dets or [DET], [SITE], repo, notifier, wind_toward_north, lambda s: "https://x/site/sq", replay_of=replay_of, cfg=P)


def test_downwind_subscriber_alerted_once():
    repo, nt = MemoryRepo(subs=[sub("north", 2000)]), MemoryNotifier()
    r1 = run(repo, nt)
    assert r1["sent"] == 1 and "wind toward your area" in nt.sent[0]["subject"]
    assert "airquality.cpcb.gov.in" in nt.sent[0]["body"]
    r2 = run(repo, nt)  # same detection again: not new, no second email
    assert r2["new_detections"] == 0 and r2["sent"] == 0 and len(nt.sent) == 1


def test_idempotent_per_detection_subscriber_even_if_reprocessed():
    repo, nt = MemoryRepo(subs=[sub("north", 2000)]), MemoryNotifier()
    run(repo, nt)
    repo.dets.clear()  # simulate a lost detection record: alert claim still prevents a duplicate
    r = run(repo, nt)
    assert r["duplicates"] == 1 and len(nt.sent) == 1


def test_not_downwind_not_notified_by_default():
    repo, nt = MemoryRepo(subs=[sub("south", -2000), sub("south-all", -2000, mode="all")]), MemoryNotifier()
    r = run(repo, nt)
    assert r["not_downwind"] == 1 and r["sent"] == 1
    assert nt.sent[0]["sub_id"] == "south-all" and "wind toward" not in nt.sent[0]["subject"]


def test_out_of_radius_ignored():
    repo, nt = MemoryRepo(subs=[sub("far", 9000)]), MemoryNotifier()
    assert run(repo, nt)["sent"] == 0


def test_uncounted_detection_ignored():
    repo, nt = MemoryRepo(subs=[sub("north", 2000)]), MemoryNotifier()
    assert run(repo, nt, dets=[dict(DET, counted=False, tier="C")])["new_detections"] == 0


def test_replay_labelled():
    repo, nt = MemoryRepo(subs=[sub("north", 2000)]), MemoryNotifier()
    r = run(repo, nt, replay_of="2026-10-08T10:00:00Z")
    assert r["sent"] == 1
    assert nt.sent[0]["subject"].startswith("REPLAY of detection from 22 Apr 2024")
    assert nt.sent[0]["body"].startswith("REPLAY.")
    assert r["alerts"][0]["replay"] is True
