"""Live watch: new counted FIRMS NRT detections -> forecast wind -> downwind check -> email alerts.

Persistence (Repo) and delivery (Notifier) are interfaces: DynamoDB/SNS in AWS (pipeline/aws/),
in-memory fakes in tests. Idempotent per (detection, subscriber) via Repo.claim_alert.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Protocol

from pipeline.attribute.attribute import attribute
from pipeline.common.config import load
from pipeline.common.geo import ang_diff, compass
from pipeline.downwind.downwind import bearing, edge_distance_m
from pipeline.firms.client import IST, SAT_NAMES, RawDetection, dedupe, parse_csv

AQI_LINE = "Official air quality for your area: https://airquality.cpcb.gov.in/AQI_India/ (CPCB). Smoulder does not give health advice."


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def round_coord(v: float) -> float:
    return round(v, 3)


class Repo(Protocol):
    def put_detection_if_new(self, det: dict, first_seen_ts: str) -> bool: ...
    def subscribers(self) -> list[dict]: ...
    def claim_alert(self, sub_id: str, det_id: str, record: dict) -> bool: ...
    def finish_alert(self, sub_id: str, det_id: str, fields: dict) -> None: ...
    def put_live(self, feed: dict) -> None: ...


class Notifier(Protocol):
    def send(self, sub: dict, subject: str, body: str) -> str: ...


@dataclass
class MemoryRepo:
    dets: dict = field(default_factory=dict)
    subs: list = field(default_factory=list)
    alerts: dict = field(default_factory=dict)
    live: dict | None = None

    def put_detection_if_new(self, det, first_seen_ts):
        if det["det_id"] in self.dets:
            return False
        self.dets[det["det_id"]] = {**det, "first_seen_ts": first_seen_ts}
        return True

    def subscribers(self):
        return list(self.subs)

    def claim_alert(self, sub_id, det_id, record):
        k = (sub_id, det_id)
        if k in self.alerts:
            return False
        self.alerts[k] = dict(record)
        return True

    def finish_alert(self, sub_id, det_id, fields):
        self.alerts[(sub_id, det_id)].update(fields)

    def put_live(self, feed):
        self.live = feed


@dataclass
class MemoryNotifier:
    sent: list = field(default_factory=list)

    def send(self, sub, subject, body):
        self.sent.append({"sub_id": sub["sub_id"], "subject": subject, "body": body})
        return f"msg-{len(self.sent)}"


def downwind_window(site: dict, lon: float, lat: float, hours: list[dict], cfg: dict | None = None) -> dict:
    """Run the downwind rule over hourly wind (forecast or, for replays, archive) for one subscriber."""
    cfg = cfg or load("downwind")
    b = bearing(site["centroid"][0], site["centroid"][1], lon, lat)
    down = [h["ts_ist"] for h in hours if h["ws_ms"] >= cfg["ws_min_ms"] and ang_diff(b, (h["wd_from_deg"] + 180.0) % 360.0) <= cfg["half_width_deg"]]
    return {
        "bearing_deg": round(b),
        "bearing_compass": compass(b),
        "downwind_hours": len(down),
        "first": down[0] if down else None,
        "last": down[-1] if down else None,
        "hours_considered": len(hours),
        "downwind": len(down) >= cfg["min_hours"],
    }


def compose(site: dict, det: dict, win: dict, dist_m: float, replay_of: str | None, site_url: str) -> tuple[str, str]:
    t = datetime.strptime(det["ts_utc"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).astimezone(IST)
    when = t.strftime("%d %b %Y, %H:%M IST")
    sat = SAT_NAMES.get(det["satellite"], det["satellite"])
    conf = {"l": "low", "n": "nominal", "h": "high"}.get(det["confidence"], det["confidence"])
    prefix = f"REPLAY of detection from {t.strftime('%d %b %Y')}: " if replay_of else ""
    if win["downwind"]:
        subject = f"{prefix}Fire detected at {site['name']}; wind toward your area for about {win['downwind_hours']} h"
    else:
        subject = f"{prefix}Fire detected at {site['name']}"
    lines = []
    if replay_of:
        lines += ["REPLAY. This is a re-run of the alert path for a real past detection, using the archived wind for that time. It is not a new fire.", ""]
    lines += [
        f"Satellite detection at {site['name']} ({site['city_name']}) at {when}.",
        f"Satellite: VIIRS {sat}. Confidence: {conf}. FRP: {det.get('frp_mw')} MW. Attribution: Tier {det['tier']} ({'pixel centre inside the site boundary' if det['tier'] == 'A' else 'pixel footprint overlaps the site boundary'}).",
        "",
    ]
    if win["downwind"]:
        lines.append(
            f"{'Archived' if replay_of else 'Forecast'} wind (Open-Meteo) blows from the site toward your area ({dist_m / 1000:.1f} km {win['bearing_compass']} of the site) "
            f"for about {win['downwind_hours']} of the next {win['hours_considered']} hours, between {win['first'][11:16]} and {win['last'][11:16]} IST."
        )
    else:
        lines.append(f"{'Archived' if replay_of else 'Forecast'} wind (Open-Meteo) does not blow toward your area in the next {win['hours_considered']} hours.")
    lines += [
        "This is a modelled wind direction, not a measurement of smoke. A detection means a satellite pixel was hot at overpass time.",
        "",
        f"Fire Record: {site_url}",
        AQI_LINE,
        "",
        "You subscribed to Smoulder alerts. To stop, use the unsubscribe link in this email.",
    ]
    return subject, "\n".join(lines)


def poll_nrt(firms, cities: dict[str, tuple], sources: list[str], day_range: int = 1) -> list[RawDetection]:
    today = datetime.now(timezone.utc).date()
    raw: list[RawDetection] = []
    for city, bbox in cities.items():
        for src in sources:
            raw.extend(parse_csv(firms.fetch_window(src, city, bbox, today - timedelta(days=day_range - 1), day_range, cache=False), src))
    return dedupe(raw)


def process(
    dets: list[dict],
    sites: list[dict],
    repo: Repo,
    notifier: Notifier,
    wind_for: callable,
    site_url: callable,
    replay_of: str | None = None,
    cfg: dict | None = None,
) -> dict:
    """Alert path for counted detections. Returns a summary for the run record.

    wind_for(site, det) -> hourly wind list (forecast for live, archive for replays).
    """
    cfg = cfg or load("downwind")
    by_id = {s["site_id"]: s for s in sites}
    first_seen = now_iso()
    new = []
    for d in dets:
        if not d["counted"]:
            continue
        if replay_of or repo.put_detection_if_new(d, first_seen):
            new.append(d)
    subs = repo.subscribers()
    sent = skipped = duplicates = 0
    log = []
    for d in new:
        site = by_id[d["site_id"]]
        hours = wind_for(site, d)
        for sub in subs:
            dist = edge_distance_m(site, sub["lon_r"], sub["lat_r"])
            if dist > cfg["radius_km"] * 1000:
                continue
            win = downwind_window(site, sub["lon_r"], sub["lat_r"], hours, cfg)
            if not win["downwind"] and sub.get("mode", "downwind") != "all":
                skipped += 1
                continue
            alert_key = d["det_id"] if not replay_of else f"replay:{d['det_id']}:{replay_of}"
            record = {"site_id": d["site_id"], "acq_ts": d["ts_utc"], "first_seen_ts": first_seen, "replay": bool(replay_of), "downwind_hours": win["downwind_hours"]}
            if not repo.claim_alert(sub["sub_id"], alert_key, record):
                duplicates += 1
                continue
            subject, body = compose(site, d, win, dist, replay_of, site_url(site))
            msg_id = notifier.send(sub, subject, body)
            sent_ts = now_iso()
            repo.finish_alert(sub["sub_id"], alert_key, {"alert_sent_ts": sent_ts, "message_id": msg_id, "subject": subject})
            sent += 1
            log.append({"det_id": d["det_id"], "site_id": d["site_id"], "sub_id": sub["sub_id"], "acq_ts": d["ts_utc"], "first_seen_ts": first_seen, "alert_sent_ts": sent_ts, "replay": bool(replay_of)})
    return {"new_detections": len(new), "subscribers": len(subs), "sent": sent, "not_downwind": skipped, "duplicates": duplicates, "alerts": log}


def live_feed(dets: list[dict], sites: list[dict], run_id: str) -> dict:
    by_id = {s["site_id"]: s for s in sites}
    counted = sorted((d for d in dets if d["counted"]), key=lambda d: d["ts_utc"])
    last = counted[-1] if counted else None
    return {
        "last_detection": {**last, "site_name": by_id[last["site_id"]]["name"]} if last else None,
        "checked_at": now_iso(),
        "run_id": run_id,
    }


def attribute_live(raw: list[RawDetection], sites: list[dict]) -> list[dict]:
    return attribute(raw, sites)


def timed(fn, *a, **kw):
    t0 = time.time()
    out = fn(*a, **kw)
    return out, time.time() - t0
