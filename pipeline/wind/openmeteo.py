"""Open-Meteo hourly 10 m wind: archive (history) and forecast (live alerts).

Archive: https://archive-api.open-meteo.com/v1/archive (verified 2026-10-08)
  models=ecmwf_ifs (9 km, 2017+) preferred; era5_land (0.1 deg) then era5 (0.25 deg) fill nulls.
Forecast: https://api.open-meteo.com/v1/forecast
Times are requested in Asia/Kolkata; wind_direction_10m is the direction the wind blows FROM.
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

import requests

from pipeline.common import store
from pipeline.common.config import USER_AGENT

ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
MODELS = ["ecmwf_ifs", "era5_land", "era5"]
MODEL_LABEL = {"ecmwf_ifs": "ECMWF IFS 9 km", "era5_land": "ERA5-Land 0.1°", "era5": "ERA5 0.25°", "forecast": "Open-Meteo forecast (best match)"}


def _get(url: str, params: dict) -> dict:
    for attempt in range(6):
        time.sleep(0.3)  # stay well under Open-Meteo's per-minute limit
        try:
            r = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                time.sleep(30 * (attempt + 1))
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt == 5:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo failed: {url}")


def _month_bounds(y: int, m: int, latest: date) -> tuple[date, date]:
    start = date(y, m, 1)
    end = (date(y + (m == 12), m % 12 + 1, 1) - timedelta(days=1))
    return start, min(end, latest)


def fetch_month(site: dict, y: int, m: int, latest: date | None = None) -> list[dict]:
    """Hourly wind for one site-month, merged across models (cached; current month not cached)."""
    latest = latest or (date.today() - timedelta(days=6))  # archive lags ~5 days
    start, end = _month_bounds(y, m, latest)
    if end < start:
        return []
    complete = end.month == m and (end + timedelta(days=1)).month != m
    key = f"raw/wind/{site['site_id']}/{y:04d}-{m:02d}.json"
    hit = store.get(key) if complete else None
    if hit is not None:
        return json.loads(hit)
    lon, lat = site["centroid"]
    by_model = {}
    for mdl in MODELS:
        by_model[mdl] = _get(
            ARCHIVE,
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "hourly": "wind_speed_10m,wind_direction_10m",
                "timezone": "Asia/Kolkata",
                "wind_speed_unit": "ms",
                "models": mdl,
            },
        )["hourly"]
    rows = merge_models(site["site_id"], by_model)
    if complete:
        store.put(key, json.dumps(rows).encode(), "application/json")
    return rows


def merge_models(site_id: str, by_model: dict[str, dict]) -> list[dict]:
    """Per hour, take the first model in MODELS order with non-null speed and direction."""
    times = by_model[MODELS[0]]["time"]
    rows = []
    for i, t in enumerate(times):
        for mdl in MODELS:
            h = by_model.get(mdl)
            if not h or i >= len(h["time"]):
                continue
            ws, wd = h["wind_speed_10m"][i], h["wind_direction_10m"][i]
            if ws is not None and wd is not None:
                rows.append({"site_id": site_id, "ts_ist": t, "ws_ms": round(ws, 2), "wd_from_deg": round(wd), "model": mdl})
                break
    return rows


def fetch_forecast(lon: float, lat: float, hours: int) -> list[dict]:
    """Next `hours` hourly winds from the forecast API (best-match model)."""
    h = _get(
        FORECAST,
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_direction_10m",
            "timezone": "Asia/Kolkata",
            "wind_speed_unit": "ms",
            "forecast_hours": hours,
        },
    )["hourly"]
    return [
        {"ts_ist": t, "ws_ms": ws, "wd_from_deg": wd, "model": "forecast"}
        for t, ws, wd in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"])
        if ws is not None and wd is not None
    ]


def fetch_recent(site: dict, start: date, end: date) -> list[dict]:
    """Days newer than the archive: use the forecast API's past_days (best-match), labelled 'forecast'."""
    lon, lat = site["centroid"]
    past = (date.today() - start).days + 1
    h = _get(
        FORECAST,
        {
            "latitude": lat,
            "longitude": lon,
            "hourly": "wind_speed_10m,wind_direction_10m",
            "timezone": "Asia/Kolkata",
            "wind_speed_unit": "ms",
            "past_days": min(past, 92),
            "forecast_days": 1,
        },
    )["hourly"]
    out = []
    for t, ws, wd in zip(h["time"], h["wind_speed_10m"], h["wind_direction_10m"]):
        d = datetime.fromisoformat(t).date()
        if start <= d <= end and ws is not None and wd is not None:
            out.append({"site_id": site["site_id"], "ts_ist": t, "ws_ms": round(ws, 2), "wd_from_deg": round(wd), "model": "forecast"})
    return out


def wind_for_fire_days(site: dict, days: list[str]) -> list[dict]:
    """Hourly wind covering each fire day and the following day (whole months, cached)."""
    latest_archive = date.today() - timedelta(days=6)
    months = set()
    recent: list[date] = []
    for d in days:
        for dd in (date.fromisoformat(d), date.fromisoformat(d) + timedelta(days=1)):
            if dd <= latest_archive:
                months.add((dd.year, dd.month))
            else:
                recent.append(dd)
    rows: list[dict] = []
    for y, m in sorted(months):
        rows.extend(fetch_month(site, y, m, latest_archive))
    if recent:
        rows.extend(fetch_recent(site, min(recent), max(recent)))
    seen, out = set(), []
    for r in sorted(rows, key=lambda r: r["ts_ist"]):
        if r["ts_ist"] not in seen:
            seen.add(r["ts_ist"])
            out.append(r)
    return out
