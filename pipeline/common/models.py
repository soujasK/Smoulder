"""Shared data contract. Mirrors web/src/types/contract.ts; tests/test_contract.py validates the snapshot."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Tier = Literal["A", "B", "C"]
MetricTier = Literal["MEASURED", "COUNTED", "ESTIMATED", "MODELLED", "COMPILED"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    id: str
    name: str
    url: str
    licence: str
    attribution: str
    used_for: str
    retrieved_on: Optional[str] = None


class SchoolPoint(Strict):
    osm: str
    name: Optional[str]
    amenity: Optional[str]
    lon: float
    lat: float
    distance_m: int


class Context(Strict):
    site_id: str
    buildings_1km: int
    buildings_3km: int
    hospitals_1km: int
    hospitals_3km: int
    schools_1km: int
    schools_3km: int
    nearest_school_m: Optional[int]
    people_1km_est: int
    people_3km_est: int
    schools: list[SchoolPoint]
    sources: dict[str, str]
    retrieved_on: str


class SiteStats(Strict):
    fire_days_by_year: dict[str, int]
    fire_days_365: int
    detections_counted: int
    detections_by_tier: dict[str, int]
    low_conf_ab: int
    max_frp_mw: Optional[float]
    last_detection_utc: Optional[str]
    first_data_date: str
    data_through: str


class Rank(Strict):
    score: Optional[float]
    position: Optional[int]
    label: str
    formula: str


class SchoolsDownwind(Strict):
    year: int
    schools_considered: int
    schools_downwind_any_day: int
    school_downwind_days: int


class Site(Strict):
    site_id: str
    name: str
    city: str
    city_name: str
    osm_id: str
    boundary_source: Literal["osm", "traced"]
    approved: bool
    demo: bool
    utm_epsg: int
    area_ha: float
    centroid: list[float]
    polygon: dict[str, Any]
    context: Optional[Context]
    stats: SiteStats
    rank: Rank
    schools_downwind: Optional[SchoolsDownwind] = None


class Detection(Strict):
    site_id: str
    det_id: str
    ts_utc: str
    date_ist: str
    source: str
    satellite: str
    confidence: str
    frp_mw: Optional[float]
    scan_km: Optional[float]
    track_km: Optional[float]
    lat: float
    lon: float
    daynight: str
    tier: Tier
    dist_m: float
    fallback_footprint: bool
    counted: bool
    low_conf_ab: bool


class FireDay(Strict):
    site_id: str
    date_ist: str
    detections: int
    tier_a: int
    tier_b: int
    low_conf_ab: int
    max_frp_mw: Optional[float]
    first_ts_utc: str
    satellites: list[str]


class Episode(Strict):
    site_id: str
    start_date: str
    end_date: str
    fire_days: int
    span_days: int
    detections: int
    max_frp_mw: Optional[float]


class WindHour(Strict):
    ts_ist: str
    ws_ms: float
    wd_from_deg: float
    model: str


class Sector(Strict):
    site_id: str
    date_ist: str
    wind_to_deg: list[int]
    date_only_fallback: bool
    radius_km: float
    geometry: dict[str, Any]


class DownwindSiteDay(Strict):
    site_id: str
    name: str
    detections: int
    max_frp_mw: Optional[float]
    window_start_ist: str
    date_only_fallback: bool
    downwind_hours: int
    downwind_at: list[str]
    calm_hours: int
    missing_hours: int
    models: list[str]


class DownwindDay(Strict):
    date_ist: str
    sites: list[DownwindSiteDay]


class NearbySite(Strict):
    site_id: str
    name: str
    distance_m: int
    bearing_deg: int
    bearing_compass: str
    fire_days: int


class DownwindResult(Strict):
    point: list[float]
    year: Optional[int]
    smoke_days: int
    days: list[DownwindDay]
    calm_days: int
    calm: list[DownwindDay]
    fire_days_nearby: int
    no_wind_days: list[str]
    nearest_sites: list[NearbySite]
    parameters: dict[str, float]
    tier: Literal["MODELLED"]


class SmokeDaysResponse(Strict):
    query: Optional[str] = None
    label: str
    status: Literal["ok", "ambiguous", "not_found", "outside_coverage"]
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    result: Optional[DownwindResult] = None
    data_through: str
    pipeline_run_id: str
    sample: bool = False


class Landmark(Strict):
    id: str
    name: str
    kind: str
    city: str
    lon: float
    lat: float
    osm: str
    results: dict[str, DownwindResult]


class ValidationEvent(Strict):
    site_id: str
    date_start: str
    date_end: str
    outlet: str
    url: str
    window: list[str]
    hit: bool
    detections: int
    max_frp_mw: Optional[float]
    detection_dates: list[str]


class Validation(Strict):
    events: list[ValidationEvent]
    hits: int
    total: int
    hit_rate: Optional[float]
    slack_days: int
    fire_days_without_news: int
    by_site: dict[str, dict[str, int]]
    note: str


class Brief(Strict):
    site_id: str
    lang: Literal["en", "hi"]
    text: str
    generator: Literal["bedrock", "template"]
    model_id: Optional[str]
    numbers_checked: bool
    label: str
    run_id: str


class BurnObs(Strict):
    site_id: str
    episode_start: str
    scene_date: str
    kind: Literal["pre", "post"]
    hot_px: Optional[int]
    burn_px: Optional[int]
    area_ha: Optional[float]
    area_ha_lo: Optional[float]
    area_ha_hi: Optional[float]
    cloud_pct: Optional[float]
    note: str
    crops: dict[str, str]


class RunStage(Strict):
    name: str
    started_at: str
    ended_at: str
    status: str
    count: Optional[int] = None


class Run(Strict):
    run_id: str
    kind: Literal["backfill", "watch", "local"]
    started_at: str
    ended_at: str
    status: str
    stages: list[RunStage]
    where: str


class Snapshot(Strict):
    pipeline_run_id: str
    generated_at: str
    data_through: str
    sample: bool
    sources: list[Source]
    parameters: dict[str, dict[str, Any]]
    sites: list[Site]
    detections: list[Detection]
    fire_days: list[FireDay]
    episodes: list[Episode]
    wind: dict[str, dict[str, list[WindHour]]]
    sectors: list[Sector]
    landmarks: list[Landmark]
    validation: Validation
    briefs: list[Brief]
    burn_obs: list[BurnObs]
    runs: list[Run]
