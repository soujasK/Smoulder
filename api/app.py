"""HTTP API (API Gateway HTTP API, payload v2) for Smoulder.

Reads the latest published snapshot from S3 (public/latest.json); subscribers/alerts/runs from DynamoDB.
/smoke-days never stores the query or the coordinates.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone

from pipeline.common import store
from pipeline.common.sites import load_sites
from pipeline.downwind.downwind import edge_distance_m, smoke_days

SNAPSHOT_TTL_S = 300
_snap: dict = {"t": 0.0, "v": None}
_hits: dict[str, list[float]] = {}
RATE = {"GET /smoke-days": (20, 60), "POST /subscribe": (5, 600), "POST /unsubscribe": (5, 600)}  # requests per window (s), per IP
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")


def resp(status: int, body, headers: dict | None = None):
    h = {"content-type": "application/json", "cache-control": "no-store"}
    h.update(headers or {})
    return {"statusCode": status, "headers": h, "body": json.dumps(body, ensure_ascii=False)}


def snapshot() -> dict:
    if _snap["v"] is None or time.time() - _snap["t"] > SNAPSHOT_TTL_S:
        _snap["v"] = store.get_json("public/latest.json")
        _snap["t"] = time.time()
    if _snap["v"] is None:
        raise RuntimeError("no published snapshot")
    return _snap["v"]


def limited(route: str, ip: str) -> bool:
    if route not in RATE:
        return False
    n, win = RATE[route]
    now = time.time()
    q = [t for t in _hits.get(f"{route}|{ip}", []) if now - t < win]
    q.append(now)
    _hits[f"{route}|{ip}"] = q
    return len(q) > n


# ---------------- geocoding (Amazon Location Service, Places v2) ----------------

def geocode(text: str, client=None) -> list[dict]:
    """Returns candidates [{label, lon, lat, score}] in India. Results are used once and not stored (IntendedUse=SingleUse)."""
    import boto3

    q = text.strip()
    if re.fullmatch(r"\d{6}", q):
        q = f"{q}, India"
    if client is None and os.environ.get("GEOCODER") == "nominatim":
        return geocode_nominatim(q)
    client = client or boto3.client("geo-places")
    r = client.geocode(QueryText=q, MaxResults=5, Filter={"IncludeCountries": ["IND"]}, IntendedUse="SingleUse", Language="en")
    out = []
    for it in r.get("ResultItems", []):
        pos = it.get("Position")
        if not pos:
            continue
        out.append({"label": it.get("Title") or q, "lon": pos[0], "lat": pos[1], "score": (it.get("MatchScores") or {}).get("Overall")})
    return out


def geocode_nominatim(q: str) -> list[dict]:
    """Local runs (SAM CLI + LocalStack have no Amazon Location): OpenStreetMap Nominatim, India only, not stored."""
    import requests

    from pipeline.common.config import USER_AGENT

    r = requests.get("https://nominatim.openstreetmap.org/search", params={"q": q, "format": "jsonv2", "countrycodes": "in", "limit": 5},
                     headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    items = r.json()
    return [{"label": it.get("display_name", q).split(", India")[0][:120], "lon": float(it["lon"]), "lat": float(it["lat"]),
             "score": 1.0 if len(items) == 1 else None} for it in items]


def wind_index(snap: dict) -> dict[str, dict[str, dict]]:
    out: dict[str, dict[str, dict]] = {}
    for sid, days in snap["wind"].items():
        d = out.setdefault(sid, {})
        for hours in days.values():
            for h in hours:
                d[h["ts_ist"]] = h
    return out


def compute(snap: dict, lon: float, lat: float, year: str) -> dict:
    sites = snap["sites"]
    fds: dict[str, list] = {}
    for f in snap["fire_days"]:
        fds.setdefault(f["site_id"], []).append(f)
    return smoke_days(lon, lat, sites, fds, wind_index(snap), year=None if year == "all" else int(year))


def in_coverage(snap: dict, lon: float, lat: float) -> bool:
    r = snap["parameters"]["downwind"]["radius_km"] * 1000
    return any(edge_distance_m(s, lon, lat) <= r for s in snap["sites"])


def smoke_days_route(qs: dict, geocoder=geocode) -> tuple[int, dict]:
    snap = snapshot()
    year = qs.get("year") or str(int(snap["data_through"][:4]) - 1)
    if year != "all" and not re.fullmatch(r"20\d\d", year):
        return 400, {"error": "year must be YYYY or all"}
    base = {"data_through": snap["data_through"], "pipeline_run_id": snap["pipeline_run_id"], "sample": False, "candidates": []}
    if qs.get("lat") and qs.get("lon"):
        try:
            lat, lon = float(qs["lat"]), float(qs["lon"])
        except ValueError:
            return 400, {"error": "bad lat/lon"}
        label = (qs.get("label") or f"{lat:.3f}, {lon:.3f}")[:120]
        cands = [{"label": label, "lon": lon, "lat": lat}]
        q = None
    else:
        q = (qs.get("q") or "").strip()[:200]
        if len(q) < 3:
            return 400, {"error": "q is required (address, landmark or PIN code)"}
        cands = geocoder(q)
        if not cands:
            return 200, {**base, "query": q, "label": q, "status": "not_found"}
        covered = [c for c in cands if in_coverage(snap, c["lon"], c["lat"])]
        top = cands[0]
        confident = len(cands) == 1 or (top.get("score") or 0) >= 0.95
        if not covered:
            return 200, {**base, "query": q, "label": top["label"], "status": "outside_coverage", "candidates": [{k: c[k] for k in ("label", "lon", "lat")} for c in cands]}
        if not confident and len(covered) > 1:
            return 200, {**base, "query": q, "label": q, "status": "ambiguous", "candidates": [{k: c[k] for k in ("label", "lon", "lat")} for c in covered]}
        cands = covered
    c = cands[0]
    if not in_coverage(snap, c["lon"], c["lat"]):
        return 200, {**base, "query": q, "label": c["label"], "status": "outside_coverage"}
    result = compute(snap, c["lon"], c["lat"], year)
    return 200, {**base, "query": q, "label": c["label"], "status": "ok", "result": result}


# ---------------- subscriptions ----------------

def subscribe_route(body: dict, geocoder=geocode) -> tuple[int, dict]:
    import boto3

    from pipeline.aws.adapters import table, to_ddb
    from pipeline.watch.watch import email_hash, round_coord

    email = (body.get("email") or "").strip()
    if not EMAIL.match(email):
        return 400, {"error": "a valid email is required"}
    mode = body.get("mode", "downwind")
    if mode not in ("downwind", "all"):
        return 400, {"error": "mode must be downwind or all"}
    if body.get("lat") is not None and body.get("lon") is not None:
        lat, lon = float(body["lat"]), float(body["lon"])
    elif body.get("location"):
        c = geocoder(str(body["location"])[:200])
        if not c:
            return 400, {"error": "location not found"}
        lat, lon = c[0]["lat"], c[0]["lon"]
    else:
        return 400, {"error": "lat/lon or location is required"}
    lat, lon = round_coord(lat), round_coord(lon)
    snap = snapshot()
    r = snap["parameters"]["downwind"]["radius_km"] * 1000
    near = [s["site_id"] for s in snap["sites"] if edge_distance_m(s, lon, lat) <= r]
    if not near:
        return 400, {"error": f"this place is more than {r / 1000:.0f} km from every tracked site"}
    # One SNS subscription per email: SNS rejects a second one with a different filter policy, so a repeat
    # subscribe reuses the existing sub_id (identical attributes are accepted) and moves it to the new place.
    from pipeline.aws.adapters import subs_by_email_hash

    existing = subs_by_email_hash(email_hash(email))
    sub_id = existing[0]["sub_id"] if existing else uuid.uuid4().hex[:16]
    sns = boto3.client("sns")
    arn = sns.subscribe(
        TopicArn=os.environ["ALERT_TOPIC_ARN"], Protocol="email", Endpoint=email, ReturnSubscriptionArn=True,
        Attributes={"FilterPolicy": json.dumps({"sub_id": [sub_id]})},
    )["SubscriptionArn"]
    table("subscribers").put_item(Item=to_ddb({
        "sub_id": sub_id, "email_hash": email_hash(email), "sns_sub_arn": arn, "lat_r": lat, "lon_r": lon,
        "site_ids": near, "mode": mode, "status": "active", "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }))
    return 200, {"status": "pending_confirmation", "message": "Amazon SNS has sent a confirmation email.", "sites": near}


def unsubscribe_route(body: dict) -> tuple[int, dict]:
    import boto3

    from pipeline.aws.adapters import subs_by_email_hash, table
    from pipeline.watch.watch import email_hash

    email = (body.get("email") or "").strip()
    if not EMAIL.match(email):
        return 400, {"error": "a valid email is required"}
    sns = boto3.client("sns")
    n = 0
    for s in subs_by_email_hash(email_hash(email)):
        arn = s.get("sns_sub_arn", "")
        if arn.startswith("arn:"):
            try:
                sns.unsubscribe(SubscriptionArn=arn)
            except Exception:  # noqa: BLE001 - pending confirmations cannot be unsubscribed; delete our record anyway
                pass
        table("subscribers").delete_item(Key={"sub_id": s["sub_id"]})
        n += 1
    return 200, {"status": "ok", "removed": n}


# ---------------- router ----------------

def handler(event, context=None):
    route = event.get("routeKey", "")
    qs = event.get("queryStringParameters") or {}
    params = event.get("pathParameters") or {}
    ip = ((event.get("requestContext") or {}).get("http") or {}).get("sourceIp", "?")
    if limited(route, ip):
        return resp(429, {"error": "too many requests"})
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode()
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return resp(400, {"error": "invalid JSON"})
    try:
        if route == "GET /meta":
            s = snapshot()
            return resp(200, {k: s[k] for k in ("pipeline_run_id", "generated_at", "data_through", "sources", "parameters")} | {"sites": [x["site_id"] for x in s["sites"]]})
        if route == "GET /snapshot":
            return resp(200, snapshot(), {"cache-control": "public, max-age=300"})
        if route == "GET /sites":
            return resp(200, [{k: v for k, v in x.items() if k != "polygon"} for x in snapshot()["sites"]])
        if route.startswith("GET /sites/{id}"):
            s = snapshot()
            site = next((x for x in s["sites"] if x["site_id"] == params.get("id")), None)
            if not site:
                return resp(404, {"error": "unknown site"})
            sid = site["site_id"]
            if route == "GET /sites/{id}":
                return resp(200, site)
            if route == "GET /sites/{id}/detections":
                lo, hi = qs.get("from", "0000"), qs.get("to", "9999")
                return resp(200, [d for d in s["detections"] if d["site_id"] == sid and lo <= d["date_ist"] <= hi])
            if route == "GET /sites/{id}/record":
                pick = lambda k: [x for x in s[k] if x["site_id"] == sid]  # noqa: E731
                return resp(200, {"site": site, "fire_days": pick("fire_days"), "episodes": pick("episodes"), "burn_obs": pick("burn_obs"), "briefs": pick("briefs"),
                                  "sectors": pick("sectors"), "validation": [e for e in s["validation"]["events"] if e["site_id"] == sid],
                                  "sources": s["sources"], "pipeline_run_id": s["pipeline_run_id"], "data_through": s["data_through"]})
            if route == "GET /sites/{id}/brief":
                lang = qs.get("lang", "en")
                b = next((x for x in s["briefs"] if x["site_id"] == sid and x["lang"] == lang), None)
                return resp(200 if b else 404, b or {"error": "no brief"})
        if route == "GET /smoke-days":
            code, out = smoke_days_route(qs)
            return resp(code, out)
        if route == "GET /imagery/{key+}":
            import boto3

            key = "imagery/" + params.get("key", "")
            if ".." in key or not re.fullmatch(r"imagery/[\w\-./]+\.(webp|png)", key):
                return resp(400, {"error": "bad key"})
            url = boto3.client("s3").generate_presigned_url("get_object", Params={"Bucket": os.environ["SMOULDER_BUCKET"], "Key": key}, ExpiresIn=3600)
            return {"statusCode": 302, "headers": {"location": url, "cache-control": "public, max-age=3000"}, "body": ""}
        if route == "GET /live":
            return resp(200, store.get_json("public/live.json") or {"last_detection": None, "checked_at": None, "run_id": None})
        if route == "GET /runs/latest":
            from pipeline.aws.adapters import recent_alerts, recent_runs

            return resp(200, {"runs": recent_runs(), "time_to_alert": recent_alerts()})
        if route == "POST /subscribe":
            code, out = subscribe_route(body)
            return resp(code, out)
        if route == "POST /unsubscribe":
            code, out = unsubscribe_route(body)
            return resp(code, out)
        if route == "POST /admin/replay":
            from pipeline.aws.tasks import replay

            if not body.get("det_id"):
                return resp(400, {"error": "det_id is required"})
            return resp(200, replay(body["det_id"], body.get("sub_id")))
    except Exception as e:  # noqa: BLE001
        print("error", route, repr(e))
        return resp(500, {"error": "internal error"})
    return resp(404, {"error": "not found"})


def sites_for_tests():
    return load_sites()
