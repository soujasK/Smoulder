from __future__ import annotations

from pipeline.common.config import load


def load_sites(approved_only: bool = True) -> list[dict]:
    sites = load("sites")["sites"]
    return [s for s in sites if s.get("approved")] if approved_only else sites


def site_by_id(site_id: str) -> dict:
    for s in load_sites(approved_only=False):
        if s["site_id"] == site_id:
            return s
    raise KeyError(site_id)
