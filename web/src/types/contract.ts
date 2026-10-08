// Shared data contract. Mirrors pipeline/common/models.py.
// tests/test_contract.py (Pydantic) and web/src/types/contract.test.ts (this file) both validate the snapshot.

export type Tier = 'A' | 'B' | 'C';
export type MetricTier = 'MEASURED' | 'COUNTED' | 'ESTIMATED' | 'MODELLED' | 'COMPILED';

export interface Source {
  id: string; name: string; url: string; licence: string; attribution: string; used_for: string; retrieved_on?: string | null;
}

export interface SchoolPoint { osm: string; name: string | null; amenity: string | null; lon: number; lat: number; distance_m: number }

export interface Context {
  site_id: string;
  buildings_1km: number; buildings_3km: number;
  hospitals_1km: number; hospitals_3km: number;
  schools_1km: number; schools_3km: number;
  nearest_school_m: number | null;
  people_1km_est: number; people_3km_est: number;
  schools: SchoolPoint[];
  sources: Record<string, string>;
  retrieved_on: string;
}

export interface SiteStats {
  fire_days_by_year: Record<string, number>;
  fire_days_365: number;
  detections_counted: number;
  detections_by_tier: Record<string, number>;
  low_conf_ab: number;
  max_frp_mw: number | null;
  last_detection_utc: string | null;
  first_data_date: string;
  data_through: string;
}

export interface Rank { score: number | null; position: number | null; label: string; formula: string }

export interface SchoolsDownwind { year: number; schools_considered: number; schools_downwind_any_day: number; school_downwind_days: number }

export interface Site {
  site_id: string; name: string; city: string; city_name: string; osm_id: string;
  boundary_source: 'osm' | 'traced'; approved: boolean; demo: boolean; utm_epsg: number;
  area_ha: number; centroid: [number, number];
  polygon: GeoJSON.Polygon | GeoJSON.MultiPolygon;
  context: Context | null;
  stats: SiteStats;
  rank: Rank;
  schools_downwind?: SchoolsDownwind | null;
}

export interface Detection {
  site_id: string; det_id: string; ts_utc: string; date_ist: string; source: string; satellite: string;
  confidence: string; frp_mw: number | null; scan_km: number | null; track_km: number | null;
  lat: number; lon: number; daynight: string; tier: Tier; dist_m: number;
  fallback_footprint: boolean; counted: boolean; low_conf_ab: boolean;
}

export interface FireDay {
  site_id: string; date_ist: string; detections: number; tier_a: number; tier_b: number; low_conf_ab: number;
  max_frp_mw: number | null; first_ts_utc: string; satellites: string[];
}

export interface Episode {
  site_id: string; start_date: string; end_date: string; fire_days: number; span_days: number; detections: number; max_frp_mw: number | null;
}

export interface WindHour { ts_ist: string; ws_ms: number; wd_from_deg: number; model: string }

export interface Sector {
  site_id: string; date_ist: string; wind_to_deg: number[]; date_only_fallback: boolean; radius_km: number;
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon;
}

export interface DownwindSiteDay {
  site_id: string; name: string; detections: number; max_frp_mw: number | null; window_start_ist: string;
  date_only_fallback: boolean; downwind_hours: number; downwind_at: string[]; calm_hours: number; missing_hours: number; models: string[];
}

export interface DownwindDay { date_ist: string; sites: DownwindSiteDay[] }

export interface NearbySite { site_id: string; name: string; distance_m: number; bearing_deg: number; bearing_compass: string; fire_days: number }

export interface DownwindResult {
  point: [number, number]; year: number | null; smoke_days: number; days: DownwindDay[]; calm_days: number; calm: DownwindDay[];
  fire_days_nearby: number; no_wind_days: string[]; nearest_sites: NearbySite[]; parameters: Record<string, number>; tier: 'MODELLED';
}

export interface SmokeDaysResponse {
  query?: string | null; label: string; status: 'ok' | 'ambiguous' | 'not_found' | 'outside_coverage';
  candidates: { label: string; lon: number; lat: number }[];
  result?: DownwindResult | null; data_through: string; pipeline_run_id: string; sample: boolean;
}

export interface Landmark { id: string; name: string; kind: string; city: string; lon: number; lat: number; osm: string; results: Record<string, DownwindResult> }

export interface ValidationEvent {
  site_id: string; date_start: string; date_end: string; outlet: string; url: string; window: [string, string];
  hit: boolean; detections: number; max_frp_mw: number | null; detection_dates: string[];
}

export interface Validation {
  events: ValidationEvent[]; hits: number; total: number; hit_rate: number | null; slack_days: number;
  fire_days_without_news: number; by_site: Record<string, { fire_days: number; unreported: number }>; note: string;
}

export interface Brief {
  site_id: string; lang: 'en' | 'hi'; text: string; generator: 'bedrock' | 'template'; model_id: string | null;
  numbers_checked: boolean; label: string; run_id: string;
}

export interface BurnObs {
  site_id: string; episode_start: string; scene_date: string; kind: 'pre' | 'post';
  hot_px: number | null; burn_px: number | null; area_ha: number | null; area_ha_lo: number | null; area_ha_hi: number | null;
  cloud_pct: number | null; note: string; crops: Record<string, string>;
}

export interface RunStage { name: string; started_at: string; ended_at: string; status: string; count?: number | null }

export interface Run { run_id: string; kind: 'backfill' | 'watch' | 'local'; started_at: string; ended_at: string; status: string; stages: RunStage[]; where: string }

export interface Snapshot {
  pipeline_run_id: string; generated_at: string; data_through: string; sample: boolean;
  sources: Source[];
  parameters: Record<string, Record<string, unknown>>;
  sites: Site[]; detections: Detection[]; fire_days: FireDay[]; episodes: Episode[];
  wind: Record<string, Record<string, WindHour[]>>;
  sectors: Sector[]; landmarks: Landmark[]; validation: Validation; briefs: Brief[]; burn_obs: BurnObs[]; runs: Run[];
}

export const SNAPSHOT_KEYS: (keyof Snapshot)[] = [
  'pipeline_run_id', 'generated_at', 'data_through', 'sample', 'sources', 'parameters', 'sites', 'detections',
  'fire_days', 'episodes', 'wind', 'sectors', 'landmarks', 'validation', 'briefs', 'burn_obs', 'runs',
];
