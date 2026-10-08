from conftest import CX, CY, EPSG, square_site

from pipeline.common.geo import unproject_point
from pipeline.downwind.downwind import sector_geojson, smoke_days

P = {"radius_km": 5.0, "window_hours": 6, "ws_min_ms": 1.0, "half_width_deg": 30, "min_hours": 1}
# 08:00 UTC = 13:30 IST -> window hours 13..18 IST
FD = {"site_id": "sq", "date_ist": "2024-04-21", "detections": 2, "max_frp_mw": 4.0, "first_ts_utc": "2024-04-21T08:00Z"}


def wind(wd_from, ws=3.0, hours=range(13, 19), day="2024-04-21"):
    return {f"{day}T{h:02d}:00": {"ws_ms": ws, "wd_from_deg": wd_from, "model": "ecmwf_ifs"} for h in hours}


def point_north(dist_m=2000):
    return unproject_point(CX, CY + dist_m, EPSG)


def run(w, pt=None, fds=None):
    lon, lat = pt or point_north()
    return smoke_days(lon, lat, [square_site()], {"sq": fds or [FD]}, {"sq": w}, year=2024, cfg=P)


def test_downwind_when_wind_from_south():
    r = run(wind(180))  # blowing toward north; the point is north
    assert r["smoke_days"] == 1 and r["days"][0]["sites"][0]["downwind_hours"] == 6
    assert r["tier"] == "MODELLED" and r["parameters"] == P


def test_half_width_boundary():
    # geodesic bearing to a grid-north point is ~358.9 deg (UTM convergence ~1.1 deg here)
    assert run(wind(180 + 27))["smoke_days"] == 1
    assert run(wind(180 + 33))["smoke_days"] == 0
    assert run(wind(180 - 27))["smoke_days"] == 1


def test_upwind_not_counted():
    assert run(wind(0))["smoke_days"] == 0


def test_calm_hours_separate():
    r = run(wind(180, ws=0.5))
    assert r["smoke_days"] == 0 and r["calm_days"] == 1
    assert r["calm"][0]["sites"][0]["calm_hours"] == 6


def test_radius_cutoff():
    assert run(wind(180), pt=point_north(500 + 4900))["smoke_days"] == 1
    r = run(wind(180), pt=point_north(500 + 5100))
    assert r["smoke_days"] == 0 and r["nearest_sites"] == []


def test_date_only_fallback_flagged():
    r = run(wind(180, hours=range(0, 24)), fds=[dict(FD, first_ts_utc=None)])
    s = r["days"][0]["sites"][0]
    assert s["date_only_fallback"] is True and s["downwind_hours"] == 24


def test_window_limits_hours():
    w = wind(0)
    w["2024-04-21T20:00"] = {"ws_ms": 3.0, "wd_from_deg": 180, "model": "ecmwf_ifs"}  # outside 13..18
    assert run(w)["smoke_days"] == 0


def test_year_filter():
    assert run(wind(180), fds=[dict(FD, date_ist="2023-04-21")])["smoke_days"] == 0


def test_sector_geojson():
    f = sector_geojson(square_site(), FD, wind(180), cfg=P)
    assert f["geometry"]["type"] == "Polygon" and f["properties"]["wind_to_deg"] == [0] * 6
    assert sector_geojson(square_site(), FD, wind(180, ws=0.2), cfg=P) is None
