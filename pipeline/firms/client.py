"""NASA FIRMS area API client: windowed fetch, raw CSV cache, parse, dedupe.

Endpoint (verified 2026-10-08, https://firms.modaps.eosdis.nasa.gov/api/area/):
  /api/area/csv/{MAP_KEY}/{SOURCE}/{west,south,east,north}/{DAY_RANGE}/{YYYY-MM-DD}
DAY_RANGE 1..5, the date is the first day of the window.
"""
from __future__ import annotations

import csv
import hashlib
import io
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import requests

from pipeline.common import store
from pipeline.common.config import USER_AGENT, firms_key, load

log = logging.getLogger(__name__)
IST = timezone(timedelta(hours=5, minutes=30))

SAT_NAMES = {"N": "Suomi NPP", "N20": "NOAA-20", "1": "NOAA-20", "N21": "NOAA-21", "2": "NOAA-21", "T": "Terra", "A": "Aqua"}


@dataclass(frozen=True)
class RawDetection:
    lat: float
    lon: float
    ts_utc: datetime
    source: str
    satellite: str
    instrument: str
    confidence: str
    frp_mw: float | None
    scan_km: float | None
    track_km: float | None
    daynight: str
    bright_ti4: float | None
    type: str | None

    @property
    def date_ist(self) -> str:
        return self.ts_utc.astimezone(IST).date().isoformat()

    @property
    def det_id(self) -> str:
        k = self.dedupe_key
        return hashlib.sha1("|".join(map(str, k)).encode()).hexdigest()[:12]

    @property
    def dedupe_key(self) -> tuple:
        return (round(self.lat, 4), round(self.lon, 4), self.ts_utc.strftime("%Y-%m-%d"), self.ts_utc.strftime("%H%M"), self.satellite)


def _f(v: str | None) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def parse_csv(text: str, source: str) -> list[RawDetection]:
    """Parse a FIRMS area CSV. acq_time is HHMM in UTC (leading zeros may be dropped)."""
    text = text.strip()
    if not text or not text.startswith("latitude"):
        if text and not text.startswith("latitude"):
            raise ValueError(f"FIRMS returned non-CSV for {source}: {text[:200]}")
        return []
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        t = row["acq_time"].strip().zfill(4)
        ts = datetime.strptime(f"{row['acq_date']} {t}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)
        out.append(
            RawDetection(
                lat=float(row["latitude"]),
                lon=float(row["longitude"]),
                ts_utc=ts,
                source=source,
                satellite=str(row.get("satellite", "")).strip(),
                instrument=str(row.get("instrument", "")).strip(),
                confidence=str(row.get("confidence", "")).strip(),
                frp_mw=_f(row.get("frp")),
                scan_km=_f(row.get("scan")),
                track_km=_f(row.get("track")),
                daynight=str(row.get("daynight", "")).strip(),
                bright_ti4=_f(row.get("bright_ti4") or row.get("brightness")),
                type=(row.get("type") or None),
            )
        )
    return out


def dedupe(dets: list[RawDetection]) -> list[RawDetection]:
    seen: dict[tuple, RawDetection] = {}
    for d in dets:
        # Prefer SP over NRT when both exist for the same pixel/overpass.
        prev = seen.get(d.dedupe_key)
        if prev is None or (prev.source.endswith("_NRT") and d.source.endswith("_SP")):
            seen[d.dedupe_key] = d
    return sorted(seen.values(), key=lambda d: (d.ts_utc, d.lat, d.lon))


class Firms:
    def __init__(self, key: str | None = None):
        self.cfg = load("firms")
        self.key = key or firms_key()
        self._last = 0.0
        self._lock = threading.Lock()
        self.requests_made = 0

    def _throttle(self) -> None:
        """Space request starts by min_interval_s across all worker threads."""
        with self._lock:
            wait = self.cfg["min_interval_s"] - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def fetch_window(self, source: str, city: str, bbox: tuple[float, float, float, float], start: date, days: int, cache: bool = True) -> str:
        """Fetch one window (cached). bbox is west,south,east,north."""
        key = f"raw/firms/{source}/{city}/{start.isoformat()}_{days}d.csv"
        if cache:
            hit = store.get(key)
            if hit is not None:
                return hit.decode()
        area = ",".join(f"{v:.4f}" for v in bbox)
        url = f"{self.cfg['base']}/{self.key}/{source}/{area}/{days}/{start.isoformat()}"
        attempt = 0
        while attempt < 5:
            self._throttle()
            try:
                r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
            except requests.RequestException as e:
                log.warning("FIRMS network error %s (attempt %d)", e, attempt)
                attempt += 1
                time.sleep(2**attempt * 5)
                continue
            self.requests_made += 1
            body = r.text
            if r.status_code == 200 and (body.startswith("latitude") or body.strip() == ""):
                if cache:
                    store.put(key, body.encode(), "text/csv")
                return body
            # Over the transaction limit FIRMS answers "Invalid MAP_KEY." (HTTP 400), not 429.
            if "Exceeding" in body or r.status_code == 429 or self.over_limit():
                log.warning("FIRMS transaction limit reached, sleeping 90 s")
                time.sleep(90)
                continue  # rate-limit waits do not use up attempts
            log.warning("FIRMS %s: HTTP %s %s", source, r.status_code, body[:200])
            attempt += 1
            time.sleep(2**attempt * 5)
        raise RuntimeError(f"FIRMS failed for {source} {city} {start}")

    def status(self) -> dict:
        r = requests.get(f"https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY={self.key}", headers={"User-Agent": USER_AGENT}, timeout=30)
        r.raise_for_status()
        return r.json()

    def over_limit(self) -> bool:
        try:
            s = self.status()
        except (requests.RequestException, ValueError):
            return False
        return s.get("current_transactions", 0) >= s.get("transaction_limit", 5000) * 0.95

    def fetch_range(self, source: str, city: str, bbox, start: date, end: date, cache_until: date | None = None) -> list[RawDetection]:
        """Fetch [start, end] inclusive in windows. Windows ending after cache_until are not cached (NRT may change)."""
        w = self.cfg["window_days"]
        windows = []
        d = start
        while d <= end:
            days = min(w, (end - d).days + 1)
            cacheable = cache_until is None or d + timedelta(days=days - 1) <= cache_until
            windows.append((d, days, cacheable))
            d += timedelta(days=days)
        with ThreadPoolExecutor(max_workers=self.cfg["workers"]) as ex:
            texts = list(ex.map(lambda wd: self.fetch_window(source, city, bbox, wd[0], wd[1], cache=wd[2]), windows))
        out: list[RawDetection] = []
        for t in texts:
            out.extend(parse_csv(t, source))
        return out

    def availability(self) -> dict[str, tuple[date, date]]:
        for _ in range(20):
            r = requests.get(f"https://firms.modaps.eosdis.nasa.gov/api/data_availability/csv/{self.key}/ALL", headers={"User-Agent": USER_AGENT}, timeout=60)
            if r.status_code == 200 or not self.over_limit():
                break
            log.warning("FIRMS transaction limit reached (availability), sleeping 60 s")
            time.sleep(60)
        r.raise_for_status()
        out = {}
        for row in csv.DictReader(io.StringIO(r.text)):
            out[row["data_id"]] = (date.fromisoformat(row["min_date"]), date.fromisoformat(row["max_date"]))
        return out
