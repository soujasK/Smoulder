"""Day-1 gate: do counted detections line up with reported Delhi landfill fires?

Usage: python -m pipeline.validate.gate   (after pipeline.firms.backfill)
Writes cache/derived/validation.json and docs/GATE.md. Exit code 1 if the gate fails.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date

from pipeline.common import store
from pipeline.common.config import ROOT
from pipeline.common.sites import load_sites
from pipeline.validate.validate import gate, load_news, validate


def main() -> int:
    dets = store.get_json("derived/detections.json")
    fds = store.get_json("derived/fire_days.json")
    meta = store.get_json("derived/backfill_meta.json")
    sites = load_sites()
    ids = {s["site_id"] for s in sites}
    delhi = {s["site_id"] for s in sites if s["city"] == "delhi"}
    res = validate(load_news(), dets, fds, ids)
    store.put_json("derived/validation.json", res, indent=1)
    ok, rate = gate(res, delhi)

    tiers = Counter((x["site_id"], x["tier"]) for x in dets)
    per_year = Counter((f["site_id"], f["date_ist"][:4]) for f in fds)
    years = sorted({y for _, y in per_year})
    L = [
        "# Day-1 gate",
        "",
        f"Generated {date.today().isoformat()} by `python -m pipeline.validate.gate` from real FIRMS data (no fixtures).",
        "",
        f"**Result: {'PASS' if ok else 'FAIL'}.** Delhi news events with a counted (Tier A/B) detection within ±{res['slack_days']} day: "
        f"{sum(e['hit'] for e in res['events'] if e['site_id'] in delhi)} of {sum(1 for e in res['events'] if e['site_id'] in delhi)}"
        f" ({rate:.0%}). Threshold: 50%." if rate is not None else "**Result: FAIL** (no Delhi events).",
        "",
        "## Events",
        "",
        "| Site | Reported | Outlet | Hit | Counted detections | Detection dates (IST) | Max FRP (MW) |",
        "|---|---|---|---|---|---|---|",
    ]
    for e in res["events"]:
        rep = e["date_start"] if e["date_start"] == e["date_end"] else f"{e['date_start']} to {e['date_end']}"
        L.append(
            f"| {e['site_id']} | {rep} | [{e['outlet']}]({e['url']}) | {'hit' if e['hit'] else 'miss'} | {e['detections']} | "
            f"{', '.join(e['detection_dates']) or '-'} | {e['max_frp_mw'] if e['max_frp_mw'] is not None else '-'} |"
        )
    L += [
        "",
        "## Detections by tier",
        "",
        "| Site | Tier A | Tier B | Tier C (not counted) |",
        "|---|---|---|---|",
    ]
    for s in sorted(ids):
        L.append(f"| {s} | {tiers[(s, 'A')]} | {tiers[(s, 'B')]} | {tiers[(s, 'C')]} |")
    L += ["", "## Fire days per year (counted A/B, nominal/high confidence)", "", "| Site | " + " | ".join(years) + " |", "|---|" + "---|" * len(years)]
    for s in sorted(ids):
        L.append(f"| {s} | " + " | ".join(str(per_year[(s, y)]) for y in years) + " |")
    L += [
        "",
        f"Detected fire days with no news report in the compiled list: {res['fire_days_without_news']} (the list is short; this is not a claim that those fires went unreported).",
        "",
        "## Inputs",
        "",
        f"- Sources: {', '.join(meta['availability'].keys())}; availability {json.dumps(meta['availability'])}",
        f"- City bboxes (W,S,E,N): {json.dumps(meta['cities'])}",
        f"- Raw detections after dedupe: {meta['raw_rows_deduped']}; attributed to a site (A/B/C): {meta['attributed']}",
        "- News list: `data/news_fires.csv` (each row links to its source).",
        "",
        "## Caveats",
        "",
        "- VIIRS pixels (~375 m) are larger than half of each site; Tier B can include fires just outside the boundary.",
        "- Overpasses are about twice a day per satellite; short fires between overpasses are missed. Cloud and smoke can hide fires.",
        "- Reported dates are when news said the fire began; night overpasses after midnight IST fall on the next date, hence ±1 day.",
    ]
    (ROOT / "docs" / "GATE.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
