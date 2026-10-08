# Method

The in-app Method page (`/method`) renders this with the live parameters. All thresholds are in `config/*.yaml`.

## Tiers
MEASURED (instrument), COUNTED (OSM-mapped features), ESTIMATED (gridded statistics), MODELLED (rule on model wind), COMPILED (linked news).

## 1. Sites
OSM `landuse=landfill` polygons (Ghazipur way/76727509, Bhalswa way/414943488, Okhla way/608169272, Deonar way/289511744, Kanjur way/257455760). Brahmapuram was traced on Sentinel-2 L2A (scene S2B_43PFM_20260323_0_L2A) because OSM maps only the 6.5 ha plant; the trace is in `config/traced/brahmapuram.geojson`. Added 11 Oct 2026: Perungudi way/84106307, Kodungaiyur way/29199633 (Chennai), Dhapa way/325363390 (Kolkata). Distances are computed in each site's UTM zone (43N, 44N, 45N). Pirana (Ahmedabad) was evaluated and left out (docs/ASSUMPTIONS.md §29).

## 2. Detections
FIRMS VIIRS 375 m, SNPP + NOAA-20: SP archive 2019-01-01 to the latest SP date, NRT afterwards. One bbox per city (frozen in `config/city_bboxes.yaml`), 5-day windows, raw CSV cached. Dedupe key: (lat 4 dp, lon 4 dp, date, time, satellite), preferring SP. Detections NASA flags as `type=2` (static land source) are never counted.

## 3. Attribution
Footprint = `scan × track` km rectangle at the pixel centre (fallback 0.375 km, flagged).
- Tier A: centre inside the polygon. Tier B: footprint intersects, centre outside. Tier C: within 2 km, no intersection (never counted).
- Counted = A/B with nominal or high confidence. Fire day = IST date with ≥ 1 counted detection. Episode = fire days with gaps ≤ 1 day.

## 4. Wind
Open-Meteo archive hourly 10 m wind: ECMWF IFS 9 km, else ERA5-Land, else ERA5 (model stored per hour). Forecast API for live alerts and days not yet archived.

## 5. Smoke Days (MODELLED)
For point P and site S: skip if the edge distance > 5 km. b = geodesic bearing centroid → P. For the 6 hourly samples from the IST hour of the first counted detection: downwind if ws ≥ 1 m/s and |b − (wd_from + 180)| ≤ 30°; calm if ws < 1 m/s. Smoke Day = a fire day of any site within 5 km with ≥ 1 downwind hour. The same rule is applied to each OSM school within 3 km.

## 6. Burn Scan (MEASURED, imagery)
Clear scenes (cloud < 30 %, ≥ 80 % clear SCL over the site) within 10 days before and after an episode. On a 20 m grid inside the polygon: NBR = (B8A − B12)/(B8A + B12); dNBR = NBR_pre − NBR_post; burn-like change where dNBR > 0.27 and both scenes are clear. Hot surface (heuristic): B12 > 0.5, B12 > B11 > B8A. Area = pixels × 0.04 ha; range = ± half the boundary pixels × 0.04 ha (plus cloudy boundary pixels). Crops: SWIR composite B12/B8A/B4, linear 2–98 % stretch.

## 7. Context
OSM buildings, schools and hospitals inside the polygon buffered by 1 and 3 km (COUNTED). WorldPop 2020 summed over the same rings (ESTIMATED).

## 8. Ranking
score = fire_days_last_365 × log10(1 + people_1km_est). Sites with 0 fire days in the last 365 days: "no detections", not ranked.

## 9. Validation
A news event is a hit if a counted detection falls within [start − 1, end + 1] (IST). Gate: ≥ 50 % of Delhi events hit (result in `docs/GATE.md`).

## 10. Briefs
Bedrock Converse on a strict JSON of the record's numbers; every number in the output must appear in the JSON, banned words linted; up to 2 regenerations, then the deterministic template.

## 11. Alerts
Every 30 min: FIRMS NRT (SNPP, NOAA-20, NOAA-21, last day) → attribute → conditional put in `detections` (new?) → 12 h forecast → downwind rule per subscriber → SNS email; idempotent on (subscriber, detection) via a conditional put in `alerts`. Time to alert = alert_sent − first_seen; acquisition → alert includes FIRMS publication delay.

## Prior work
- "Waste fire surveillance: a case study using remote sensing data and IoT ground sensing", *Waste Management* (2026).
- Brahmapuram 2023 fire air-quality study, *Science of the Total Environment* (2024).
- Schroeder et al. (2014), the VIIRS 375 m active fire product; Key & Benson (2006), dNBR severity thresholds.

These citations come from the project brief; full references must be checked by a human before submission (see PROGRESS.md).
