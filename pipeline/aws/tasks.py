"""Lambda entry point for Step Functions tasks. event = {"task": <name>, ...}.

Backfill: load_sites -> fetch_firms (Map: cities) -> attribute -> site_stage (Map: sites) -> validate
          -> generate_briefs -> publish
Watch:    poll_nrt -> dedupe -> (Choice: any new?) -> alert (Map: new detections) -> update_live
Every task records its stage timing in the runs table.
"""
from __future__ import annotations

import os
import time
import traceback
from datetime import date, datetime, timedelta, timezone

from pipeline.common import store
from pipeline.common.config import load
from pipeline.common.sites import load_sites


def emf(metrics: dict[str, float], unit: str = "Count") -> None:
    """CloudWatch Embedded Metric Format: one log line becomes metrics in the Smoulder namespace."""
    import json

    print(json.dumps({"_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{"Namespace": "Smoulder", "Dimensions": [[]],
        "Metrics": [{"Name": k, "Unit": unit} for k in metrics]}]}, **metrics}))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record_stage(run_id: str, kind: str, name: str, started: str, status: str, count: int | None = None) -> None:
    from pipeline.aws.adapters import table, to_ddb

    stage = to_ddb({"name": name, "started_at": started, "ended_at": _now(), "status": status, "count": count})
    table("runs").update_item(
        Key={"run_id": run_id},
        UpdateExpression="SET stages = list_append(if_not_exists(stages, :e), :s), kind = :k, #w = :w, started_at = if_not_exists(started_at, :t), ended_at = :n, #st = if_not_exists(#st, :run)",
        ExpressionAttributeNames={"#w": "where", "#st": "status"},
        ExpressionAttributeValues={":e": [], ":s": [stage], ":k": kind, ":w": f"aws {os.environ.get('AWS_REGION', '')}", ":t": started, ":n": _now(), ":run": "RUNNING"},
    )


def finish_run(run_id: str, status: str) -> None:
    from pipeline.aws.adapters import table

    table("runs").update_item(Key={"run_id": run_id}, UpdateExpression="SET #st = :s, ended_at = :n", ExpressionAttributeNames={"#st": "status"}, ExpressionAttributeValues={":s": status, ":n": _now()})


def _cities() -> dict[str, tuple]:
    import yaml

    from pipeline.common.config import CONFIG_DIR

    return {k: tuple(v) for k, v in yaml.safe_load((CONFIG_DIR / "city_bboxes.yaml").read_text()).items()}


# ---------------- Backfill ----------------

def load_sites_task(ev):
    run_id = ev.get("run_id") or "backfill-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sites = load_sites()
    return {"run_id": run_id, "cities": sorted({s["city"] for s in sites}), "sites": [s["site_id"] for s in sites], "_count": len(sites)}


def fetch_firms_task(ev):
    from pipeline.firms.backfill import plan
    from pipeline.firms.client import Firms

    city = ev["city"]
    cfg = load("firms")
    firms = Firms()
    avail = firms.availability()
    jobs = plan({city: _cities()[city]}, avail, date.fromisoformat(cfg["start_date"]), date.today())
    rows = 0
    for src, c, bbox, lo, hi, cache_until in jobs:
        rows += len(firms.fetch_range(src, c, bbox, lo, hi, cache_until=cache_until))
    store.put_json("derived/availability.json", {k: [v[0].isoformat(), v[1].isoformat()] for k, v in avail.items()})
    return {"city": city, "rows": rows, "requests": firms.requests_made, "_count": rows}


def attribute_task(ev):
    from pipeline.firms.backfill import run

    meta = run()  # all windows are cached by fetch_firms; this re-reads them from S3
    return {"attributed": meta["attributed"], "_count": meta["attributed"]}


def site_stage_task(ev):
    """FetchWind -> FindScenes/MeasureBurn -> BuildTerrain -> FetchContext for one site."""
    from pipeline.common.sites import site_by_id
    from pipeline.context.context import build_context
    from pipeline.wind.openmeteo import wind_for_fire_days

    site = site_by_id(ev["site_id"])
    fds = [f["date_ist"] for f in store.get_json("derived/fire_days.json", []) if f["site_id"] == site["site_id"]]
    out = {"site_id": site["site_id"], "fire_days": len(fds)}
    out["wind_hours"] = len(wind_for_fire_days(site, fds))
    try:
        from pipeline.imagery.burnscan import measure_site

        out["burn_obs"] = len(measure_site(site))
    except Exception as e:  # noqa: BLE001 - imagery is best effort; the record says "no clear image"
        out["burn_obs_error"] = f"{type(e).__name__}: {e}"[:200]
    ctx = build_context(site)
    out["context"] = bool(ctx)
    out["_count"] = out["wind_hours"]
    return out


def validate_task(ev):
    from pipeline.validate.validate import load_news, validate

    dets = store.get_json("derived/detections.json")
    fds = store.get_json("derived/fire_days.json")
    res = validate(load_news(), dets, fds, {s["site_id"] for s in load_sites()})
    store.put_json("derived/validation.json", res, indent=1)
    return {"hits": res["hits"], "total": res["total"], "_count": res["hits"]}


def briefs_task(ev):
    from pipeline.briefs.bedrock import generate
    from pipeline.publish.snapshot import site_stats

    dets = store.get_json("derived/detections.json")
    fds = store.get_json("derived/fire_days.json")
    eps = store.get_json("derived/episodes.json")
    meta = store.get_json("derived/backfill_meta.json")
    through = max(v[1] for k, v in meta["availability"].items() if k.endswith("_NRT"))
    out = []
    for s in load_sites():
        from pipeline.context.context import build_context

        s = {**s, "stats": site_stats(s["site_id"], dets, fds, load("firms")["start_date"], through), "context": build_context(s)}
        for lang in ("en", "hi"):
            out.append(generate(s, eps, lang, ev["run_id"]))
    store.put_json("derived/briefs.json", out)
    return {"bedrock": sum(b["generator"] == "bedrock" for b in out), "template": sum(b["generator"] == "template" for b in out), "_count": len(out)}


def publish_task(ev):
    from pipeline.aws.adapters import batch_put
    from pipeline.publish.snapshot import build

    snap = build(run_id=ev["run_id"])
    store.put_json(f"public/{snap['pipeline_run_id']}.json", snap)
    store.put_json("public/latest.json", snap)
    n = batch_put("sites", [{k: v for k, v in s.items() if k not in ("polygon",)} | {"polygon": s["polygon"]} for s in snap["sites"]])
    n += batch_put("detections", [{**d, "sk": f"{d['ts_utc']}#{d['det_id']}"} for d in snap["detections"]])
    n += batch_put("fire_days", snap["fire_days"])
    n += batch_put("episodes", snap["episodes"])
    n += batch_put("context", [s["context"] for s in snap["sites"] if s.get("context")])
    n += batch_put("briefs", [{**b, "sk": f"{b['lang']}#{b['run_id']}"} for b in snap["briefs"]])
    n += batch_put("burn_obs", [{**b, "sk": f"{b['episode_start']}#{b['scene_date']}#{b['kind']}"} for b in snap["burn_obs"]])
    return {"snapshot": f"public/{snap['pipeline_run_id']}.json", "items_written": n, "_count": n}


# ---------------- Watch ----------------

def poll_nrt_task(ev):
    from pipeline.firms.client import Firms
    from pipeline.watch.watch import attribute_live, poll_nrt

    run_id = ev.get("run_id") or "watch-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw = poll_nrt(Firms(), _cities(), load("firms")["live_sources"], day_range=1)
    dets = [d for d in attribute_live(raw, load_sites()) if d["counted"]]
    return {"run_id": run_id, "detections": dets, "_count": len(dets)}


def dedupe_task(ev):
    from pipeline.aws.adapters import DynamoRepo
    from pipeline.watch.watch import now_iso

    repo = DynamoRepo()
    seen = now_iso()
    new = [d for d in ev["detections"] if repo.put_detection_if_new(d, seen)]
    for d in new:
        d["first_seen_ts"] = seen
    emf({"NewDetections": len(new)})
    return {"run_id": ev["run_id"], "new": new, "all": ev["detections"], "has_new": bool(new), "_count": len(new)}


def _site_url(site):
    return f"{os.environ.get('SITE_BASE_URL', '')}/site/{site['site_id']}"


def alert_task(ev):
    """One new detection: forecast wind for its site, downwind check per subscriber, SNS email."""
    from pipeline.aws.adapters import DynamoRepo, SnsNotifier
    from pipeline.watch.watch import process
    from pipeline.wind.openmeteo import fetch_forecast

    det = ev["detection"]
    sites = load_sites()
    hours_cfg = load("downwind")["forecast_hours"]
    res = process([det], sites, _AlreadyNew(DynamoRepo()), SnsNotifier(), lambda s, d: fetch_forecast(s["centroid"][0], s["centroid"][1], hours_cfg), _site_url)
    emf({"AlertsSent": res["sent"]})
    for a in res["alerts"]:
        p = lambda t: datetime.strptime(t.replace("Z", ""), "%Y-%m-%dT%H:%M:%S" if t.count(":") == 2 else "%Y-%m-%dT%H:%M")  # noqa: E731
        emf({"SeenToAlertSeconds": (p(a["alert_sent_ts"]) - p(det.get("first_seen_ts", a["first_seen_ts"]))).total_seconds(),
             "AcquisitionToAlertSeconds": (p(a["alert_sent_ts"]) - p(a["acq_ts"])).total_seconds()}, unit="Seconds")
    return {k: v for k, v in res.items() if k != "alerts"} | {"_count": res["sent"]}


class _AlreadyNew:
    """Repo wrapper: dedupe already happened in its own state."""

    def __init__(self, repo):
        self.repo = repo

    def put_detection_if_new(self, det, first_seen_ts):
        return True

    def __getattr__(self, k):
        return getattr(self.repo, k)


def update_live_task(ev):
    from pipeline.watch.watch import live_feed

    prev = store.get_json("public/live.json")
    dets = ev.get("all") or []
    feed = live_feed(dets, load_sites(), ev["run_id"])
    if feed["last_detection"] is None and prev and prev.get("last_detection"):
        feed["last_detection"] = prev["last_detection"]  # keep the last known detection between quiet polls
    store.put_json("public/live.json", feed)
    finish_run(ev["run_id"], "SUCCEEDED")
    return {"_count": len(dets)}


def replay(det_id: str, sub_id: str | None = None) -> dict:
    """Re-run the alert path for a real past detection with its archived wind. Labelled REPLAY."""
    from pipeline.aws.adapters import DynamoRepo, SnsNotifier
    from pipeline.watch.watch import now_iso, process
    from pipeline.wind.openmeteo import fetch_month

    snap = store.get_json("public/latest.json")
    det = next((d for d in snap["detections"] if d["det_id"] == det_id), None)
    if det is None:
        raise ValueError(f"unknown detection {det_id}")
    sites = load_sites()
    hours_n = load("downwind")["forecast_hours"]

    def archived(site, d):
        t = datetime.strptime(d["ts_utc"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc) + timedelta(hours=5, minutes=30)
        t = t.replace(minute=0)
        rows = fetch_month(site, t.year, t.month)
        if (t + timedelta(hours=hours_n)).month != t.month:
            nxt = t + timedelta(hours=hours_n)
            rows += fetch_month(site, nxt.year, nxt.month)
        want = {(t + timedelta(hours=k)).strftime("%Y-%m-%dT%H:00") for k in range(hours_n)}
        return [r for r in rows if r["ts_ist"] in want]

    repo = DynamoRepo()
    if sub_id:
        base = repo  # keep the real repo: `repo` is rebound to the wrapper below
        only = [s for s in base.subscribers() if s["sub_id"] == sub_id]

        class One:
            def __getattr__(self, k):
                return getattr(base, k)

            def subscribers(self):
                return only

        repo = One()
    run_id = "replay-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    t0 = _now()
    res = process([det], sites, repo, SnsNotifier(), archived, _site_url, replay_of=now_iso())
    record_stage(run_id, "watch", "Replay", t0, "SUCCEEDED", res["sent"])
    finish_run(run_id, "SUCCEEDED")
    return {"run_id": run_id, **{k: v for k, v in res.items() if k != "alerts"}, "alerts": res["alerts"]}


TASKS = {
    "load_sites": ("backfill", "LoadSites", load_sites_task),
    "fetch_firms": ("backfill", "FetchFirmsWindows", fetch_firms_task),
    "attribute": ("backfill", "Attribute", attribute_task),
    "site_stage": ("backfill", "SiteStage", site_stage_task),
    "validate": ("backfill", "Validate", validate_task),
    "generate_briefs": ("backfill", "GenerateBriefs", briefs_task),
    "publish": ("backfill", "PublishSnapshot", publish_task),
    "poll_nrt": ("watch", "PollNRT", poll_nrt_task),
    "dedupe": ("watch", "Dedupe", dedupe_task),
    "alert": ("watch", "AlertSubscribers", alert_task),
    "update_live": ("watch", "UpdateLiveFeed", update_live_task),
}


def handler(event, context=None):
    task = event["task"]
    kind, stage_name, fn = TASKS[task]
    started = _now()
    t0 = time.time()
    try:
        out = fn(event)
    except Exception:
        run_id = event.get("run_id")
        if run_id:
            record_stage(run_id, kind, stage_name, started, "FAILED")
            finish_run(run_id, "FAILED")
        traceback.print_exc()
        raise
    run_id = out.get("run_id") or event.get("run_id")
    if run_id:
        suffix = f" {event['city']}" if "city" in event else f" {event['site_id']}" if "site_id" in event else ""
        record_stage(run_id, kind, stage_name + suffix, started, "SUCCEEDED", out.pop("_count", None))
        if task == "publish":
            finish_run(run_id, "SUCCEEDED")
    out.pop("_count", None)
    out.setdefault("run_id", run_id)
    print({"task": task, "seconds": round(time.time() - t0, 1)})
    return out
