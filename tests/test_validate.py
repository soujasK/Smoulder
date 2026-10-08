from pipeline.validate.validate import gate, validate

NEWS = [
    {"site_id": "a", "date_start": "2024-04-21", "date_end": "2024-04-21", "outlet": "X", "url": "u1"},
    {"site_id": "a", "date_start": "2022-03-28", "date_end": "2022-03-30", "outlet": "X", "url": "u2"},
    {"site_id": "b", "date_start": "2023-01-01", "date_end": "2023-01-01", "outlet": "X", "url": "u3"},
]


def d(site, day, counted=True, frp=3.0):
    return {"site_id": site, "date_ist": day, "counted": counted, "frp_mw": frp}


def test_hit_within_slack_and_miss():
    dets = [d("a", "2024-04-22"), d("a", "2022-04-02"), d("b", "2023-01-01", counted=False)]
    fds = [{"site_id": "a", "date_ist": "2024-04-22"}, {"site_id": "a", "date_ist": "2022-04-02"}]
    r = validate(NEWS, dets, fds, {"a", "b"})
    assert [e["hit"] for e in r["events"]] == [True, False, False]  # uncounted (Tier C) never hits
    assert r["hits"] == 1 and r["total"] == 3
    assert r["fire_days_without_news"] == 1  # 2022-04-02 is outside 03-27..03-31
    ok, rate = gate(r, {"a"})
    assert ok is True and rate == 0.5
    assert gate(r, {"b"})[0] is False


def test_sites_filter():
    r = validate(NEWS, [], [], {"a"})
    assert r["total"] == 2
