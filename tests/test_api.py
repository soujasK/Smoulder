import json

import pytest

import api.app as app
from pipeline.common import store

SNAP = json.loads((__import__("conftest").ROOT / "web" / "public" / "data" / "snapshot.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def fixed_snapshot(monkeypatch):
    monkeypatch.setattr(app, "_snap", {"t": 1e18, "v": SNAP})
    app._hits.clear()
    writes = []
    monkeypatch.setattr(store, "put", lambda *a, **k: writes.append(a))
    return writes


def bhalaswa():
    return next(lm for lm in SNAP["landmarks"] if lm["name"] == "Bhalaswa")


def ev(route, qs=None, body=None, ip="1.2.3.4"):
    return {"routeKey": route, "queryStringParameters": qs, "body": json.dumps(body) if body else None, "requestContext": {"http": {"sourceIp": ip}}}


def test_smoke_days_matches_snapshot_and_writes_nothing(fixed_snapshot):
    lm = bhalaswa()
    geo = lambda q: [{"label": "Bhalaswa", "lon": lm["lon"], "lat": lm["lat"], "score": 1.0}]  # noqa: E731
    code, out = app.smoke_days_route({"q": "Bhalaswa metro", "year": "all"}, geocoder=geo)
    assert code == 200 and out["status"] == "ok"
    assert out["result"]["smoke_days"] == lm["results"]["all"]["smoke_days"]
    assert [d["date_ist"] for d in out["result"]["days"]] == [d["date_ist"] for d in lm["results"]["all"]["days"]]
    assert out["result"]["parameters"] == SNAP["parameters"]["downwind"]
    assert fixed_snapshot == []  # nothing persisted


def test_smoke_days_outside_and_ambiguous():
    far = lambda q: [{"label": "Chennai", "lon": 80.27, "lat": 13.08, "score": 1.0}]  # noqa: E731
    assert app.smoke_days_route({"q": "Chennai", "year": "2024"}, geocoder=far)[1]["status"] == "outside_coverage"
    lm = bhalaswa()
    two = lambda q: [{"label": "A", "lon": lm["lon"], "lat": lm["lat"], "score": 0.6}, {"label": "B", "lon": lm["lon"] + 0.001, "lat": lm["lat"], "score": 0.6}]  # noqa: E731
    out = app.smoke_days_route({"q": "station", "year": "2024"}, geocoder=two)[1]
    assert out["status"] == "ambiguous" and len(out["candidates"]) == 2
    assert app.smoke_days_route({"q": "zzzz", "year": "2024"}, geocoder=lambda q: [])[1]["status"] == "not_found"


def test_smoke_days_validates_input():
    assert app.smoke_days_route({"q": "x"})[0] == 400
    assert app.smoke_days_route({"q": "Delhi", "year": "1999x"})[0] == 400


def test_rate_limit():
    codes = [app.handler(ev("GET /smoke-days", {"q": "ab"}))["statusCode"] for _ in range(22)]
    assert codes[-1] == 429 and codes[0] == 400


def test_site_routes():
    r = app.handler({"routeKey": "GET /sites/{id}/record", "pathParameters": {"id": "bhalswa"}})
    body = json.loads(r["body"])
    assert r["statusCode"] == 200 and body["site"]["site_id"] == "bhalswa" and body["fire_days"]
    assert app.handler({"routeKey": "GET /sites/{id}", "pathParameters": {"id": "nope"}})["statusCode"] == 404
