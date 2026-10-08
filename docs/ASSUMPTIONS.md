# Assumptions and decisions

Each entry: the decision, why, and where it lives. Thresholds are in `config/*.yaml`, not in code.

## Data and method

1. **Counted history uses VIIRS SNPP + NOAA-20 only.** SP (standard processing) archive from 2019-01-01 to the latest SP date (2026-06-30 at build time), then NRT for the gap to today. NOAA-21 has only NRT (from 2024-01-17); adding it would add a third satellite from 2024 and make years less comparable, so NOAA-21 is used in the **live watch only**. `config/firms.yaml`.
2. **FIRMS transaction cost.** A 5-day area request over a city bbox costs about 10 transactions (measured: 5000 transactions used after about 500 requests). Over the limit, FIRMS replies `HTTP 400 Invalid MAP_KEY.`, not 429; the client checks `mapkey_status` to tell the two apart and waits. Throttle: one request start per 1.4 s, 3 workers.
3. **One bbox per city.** The union of site polygons buffered by 3 km + 2 km (Tier C radius).
4. **Pixel footprint** is an axis-aligned rectangle `scan x track` km centred on the pixel centre. The true footprint is rotated by the orbit inclination (about 8 degrees at these latitudes) and VIIRS pixels overlap; we ignore both. Fallback 0.375 x 0.375 km when scan/track are missing (flagged `fallback_footprint`).
5. **Each detection is assigned to at most one site:** best tier, then nearest.
6. **Low-confidence (`l`) A/B detections are not counted** in fire days (shown in a separate column). `config/attribution.yaml: count_low_confidence: false`.
7. **Fire day** is an IST date. Night overpasses (~01:30 IST) fall on the next calendar date after a fire reported in the evening; validation therefore allows +/-1 day.
8. **Episode gap rule:** consecutive fire days may be separated by at most `gap_days` (1) days without a detection.
9. **Wind** comes from Open-Meteo archive, preferring `ecmwf_ifs` (9 km), filling missing hours from `era5_land`, then `era5`. The model used is stored per hour. Days newer than the archive (~5-day lag) use the forecast API `past_days` (labelled `forecast`).
10. **Downwind window:** the H=6 hourly samples starting at the IST hour of the first counted detection of that fire day. Bearing is geodesic (WGS84) from the site centroid; distance is from the polygon edge in UTM 43N. Calm days = fire days within R with no downwind hour but at least one calm hour.
11. **Smoke Days default year** in the UI is the year with the most recent full data; the selector also offers each year since 2019. Numbers are small (a few days a year at most sites), and we show them as they are.
12. **Population:** WorldPop 2020 unconstrained 100 m (`wpgppop`) via the WorldPop stats API (sum over the ring polygon). 2020 is the latest year in that series. Tier: ESTIMATED.
13. **OSM counts** are counts of mapped features (`building=*` ways/relations; `amenity=school|college|kindergarten`; `amenity=hospital|clinic`) inside the polygon buffered by 1 km / 3 km. Rings include the site itself. Tier: COUNTED ("OSM-mapped").
14. **Terrain** is Copernicus DEM GLO-30, a surface model (it includes buildings and trees). Acquisition 2011-2015, so landfill heights today differ. Drape: most recent Sentinel-2 L2A scene with <1% cloud (or the clearest of the last 200 days).
15. **Ranking** `score = fire_days_last_365 x log10(1 + people_1km_est)`; "last 365" counts back from the latest data date. Sites with 0 fire days are labelled "no detections" and not ranked.

## Sites

16. Polygons are OSM `landuse=landfill` ways, chosen by the agent from Overpass candidates (largest named polygon at each known site) and marked `approved: true` **provisionally**. They still need a human check against imagery (see the human-verification list in `docs/PROGRESS.md`).
17. **Brahmapuram boundary is traced, not OSM.** The first choice (unnamed 60.3 ha way/1417183060) turned out to be cleared bare earth east of the river; the March 2023 fire detections clustered on the grey waste surface west of it, around the named 6.5 ha plant polygon (way/1262085027). The 24.5 ha boundary was traced on Sentinel-2 S2B_43PFM_20260323 (`config/traced/brahmapuram.geojson`, `boundary_source: traced`). This changed the March 2023 validation from miss to hit (18 counted detections, 3–5 Mar). Needs human review.
18. **Sixth site: Kanjur (Mumbai, 142.5 ha)**, because it has a clear named OSM boundary and shares a city bbox with Deonar (no extra FIRMS cost). Bandhwari (Gurugram) was the alternative, but its OSM polygon (11.8 ha) looks partial.
19. **Bhalswa Tier C cluster:** most Tier C detections near Bhalswa (about 300) are a recurring night-time heat source at about 28.729 N 77.156 E, inside the Rajasthani Udyog Nagar industrial area in OSM, about 1 km south of the polygon. They are not counted. This is the tiering working as intended.

25. **City bboxes are frozen** in `config/city_bboxes.yaml` because raw FIRMS cache keys do not include the bbox.
26. **Burn Scan threshold dNBR > 0.27** (moderate-low severity, Key & Benson 2006). At 0.1, normal landfill surface change gave implausible areas (Deonar 55 ha in 5 days). The metric is labelled "burn-like change". Crops use the SWIR composite B12/B8A/B4, because the B12/B11/B8A composite renders vegetation violet, which the palette bans.
27. **Smoke Days offers "All years" (2019 to date)** next to single years. The default stays the last full year, per the brief. The demo uses all years at Bhalswa (Bhalaswa station, 10 smoke days), because single-year counts are 0–4 and the Ghazipur stations had 0 smoke days in 2024 (on 21–22 Apr 2024 the wind did not blow toward them).
28. **City terrain tiles are smoothed** (Gaussian, sigma 2.5 px) and contoured every 4 m, because the surface model's buildings made 2 m contours unreadable. Site tiles are not smoothed (2 m contours).
29. **Watch Map runs per new detection**, and each task loops over subscribers, instead of a nested Map over subscribers. Same behaviour, fewer state transitions.
30. **Offline Smoke Days** works for 21 OSM stations within 4 km of the sites (precomputed with the same function the API uses; a test checks they match). Labelled "offline · precomputed".

## News list

20. `data/news_fires.csv` contains only rows whose link was opened and whose date was confirmed on 2026-10-08. The "Brahmapuram, late Feb 2025 (Onmanorama 2025-02-28)" seed could not be confirmed with a working link, so it is not included. The two undated Ghazipur fires mentioned by Down To Earth are 28 Mar 2022 and 9 Apr 2022 (Scroll.in).
21. `date_end` is the last date the source says the fire was still burning, where stated; otherwise the next day.

## Product

22. Demo landmarks are OSM railway/metro stations within 4 km of a site, never homes.
23. Hindi UI strings and template briefs were written by the agent. They are labelled as drafts and need human review before submission.
24. Briefs: the template brief is the default; Bedrock replaces it in the cloud run only if the number check passes.

## Sites added on 11 Oct 2026

25. **Four more sites, chosen for documented recurring fires:** Perungudi and Kodungaiyur (Chennai), Dhapa (Kolkata), Pirana (Ahmedabad). Boundaries are OSM ways (Perungudi: way/84106307, tagged "Pallikaranai Dumpyard"; Kodungaiyur: way/29199633; Dhapa: way/325363390; Pirana: way/321136517, tagged "Municipal Landfill" at Piplaj). Each was checked by overlaying it on the Sentinel-2 drape: all four sit on the bare dump surface.
26. Overpass mirrors were down on 11 Oct 2026, so these polygons came from `api.openstreetmap.org/api/0.6/way/<id>/full` and their demo landmarks from Nominatim (stations only, same 4 km rule). Context counts still come from Overpass.
27. Validation news added only where a report falls inside the record (2019 onward): Perungudi 27 Apr 2022 (Scroll.in) and Kodungaiyur 20 May 2022 (The News Minute). Dhapa and Pirana have well-documented fire histories (The Telegraph, Dec 2018; NGT order of 2 Jul 2019; reports from 2016 and 2017), but no dated report inside the window was found, so none was added.
28. **FIRMS static sources are never counted** (`count_static_sources: false`). NASA marks persistent heat (industry, plants) as `type=2`, "other static land source". None of the six original sites had any; the rule only affected Pirana.
29. **Pirana (Ahmedabad) was evaluated and left out.** Even without the `type=2` detections it would have had 203 fire days, 126 of them in 2023–2024. Those unflagged detections sit on the same spot as the flagged static source (around 22.979 N, 72.565 E), while the 2019–2022 detections spread across the mound. The record cannot separate landfill fires from that heat source without an ad hoc rule, so the site is not published. Its terrain, landmarks and context are cached in case a better boundary or method resolves it.
