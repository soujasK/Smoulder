from datetime import datetime, timezone

import pytest
from conftest import FIX

from pipeline.firms.client import dedupe, parse_csv

CSV = (FIX / "firms_ghazipur_2024-04-19_5d_N20.csv").read_text()


def test_parse_fixture_fields():
    dets = parse_csv(CSV, "VIIRS_NOAA20_SP")
    assert len(dets) == 4
    d = dets[3]
    assert (d.lat, d.lon) == (28.6263, 77.3252)
    assert d.ts_utc == datetime(2024, 4, 21, 20, 15, tzinfo=timezone.utc)
    assert d.satellite == "N20" and d.confidence == "n"
    assert d.frp_mw == 3.78 and d.scan_km == 0.53 and d.track_km == 0.42


def test_short_acq_time_and_ist_midnight():
    # acq_time 828 -> 08:28 UTC; 20:15 UTC on 21 Apr is 01:45 IST on 22 Apr
    dets = parse_csv(CSV, "S")
    assert (dets[0].ts_utc.hour, dets[0].ts_utc.minute) == (8, 28)
    assert dets[0].date_ist == "2024-04-19"
    assert dets[3].date_ist == "2024-04-22"


def test_empty_and_error_responses():
    assert parse_csv("", "S") == []
    assert parse_csv("latitude,longitude,acq_date,acq_time\n", "S") == []
    with pytest.raises(ValueError):
        parse_csv("Invalid MAP_KEY.", "S")


def test_dedupe_prefers_sp_over_nrt():
    out = dedupe(parse_csv(CSV, "VIIRS_NOAA20_NRT") + parse_csv(CSV, "VIIRS_NOAA20_SP"))
    assert len(out) == 4
    assert all(d.source == "VIIRS_NOAA20_SP" for d in out)
