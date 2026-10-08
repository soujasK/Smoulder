"""Compare detected fire days with the compiled news list (data/news_fires.csv).

Hit: at least one counted (Tier A/B) detection at the site within [date_start - 1, date_end + 1] (IST dates).
The news list is a validation reference, not ground truth.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from pipeline.common.config import ROOT

NEWS = ROOT / "data" / "news_fires.csv"


def load_news(path: Path = NEWS) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("url")]


def validate(news: list[dict], detections: list[dict], fire_days: list[dict], site_ids: set[str], slack_days: int = 1) -> dict:
    counted = [d for d in detections if d["counted"]]
    events = []
    for ev in news:
        if ev["site_id"] not in site_ids:
            continue
        lo = (date.fromisoformat(ev["date_start"]) - timedelta(days=slack_days)).isoformat()
        hi = (date.fromisoformat(ev["date_end"]) + timedelta(days=slack_days)).isoformat()
        ds = [d for d in counted if d["site_id"] == ev["site_id"] and lo <= d["date_ist"] <= hi]
        frps = [d["frp_mw"] for d in ds if d["frp_mw"] is not None]
        events.append(
            {
                **{k: ev[k] for k in ("site_id", "date_start", "date_end", "outlet", "url")},
                "window": [lo, hi],
                "hit": bool(ds),
                "detections": len(ds),
                "max_frp_mw": max(frps) if frps else None,
                "detection_dates": sorted({d["date_ist"] for d in ds}),
            }
        )
    covered = set()
    for ev in news:
        if ev["site_id"] not in site_ids:
            continue
        d = date.fromisoformat(ev["date_start"]) - timedelta(days=slack_days)
        end = date.fromisoformat(ev["date_end"]) + timedelta(days=slack_days)
        while d <= end:
            covered.add((ev["site_id"], d.isoformat()))
            d += timedelta(days=1)
    unreported = [f for f in fire_days if (f["site_id"], f["date_ist"]) not in covered]
    hits = sum(e["hit"] for e in events)
    by_site: dict[str, dict] = {}
    for f in fire_days:
        s = by_site.setdefault(f["site_id"], {"fire_days": 0, "unreported": 0})
        s["fire_days"] += 1
    for f in unreported:
        by_site[f["site_id"]]["unreported"] += 1
    return {
        "events": events,
        "hits": hits,
        "total": len(events),
        "hit_rate": round(hits / len(events), 3) if events else None,
        "slack_days": slack_days,
        "fire_days_without_news": len(unreported),
        "by_site": by_site,
        "note": "News list is compiled from linked reports; it is a reference, not ground truth. Absence of a report does not mean absence of a fire.",
    }


def gate(result: dict, city_sites: set[str]) -> tuple[bool, float | None]:
    evs = [e for e in result["events"] if e["site_id"] in city_sites]
    if not evs:
        return False, None
    rate = sum(e["hit"] for e in evs) / len(evs)
    return rate >= 0.5, rate
