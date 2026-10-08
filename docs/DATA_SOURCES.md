# Data sources (verified 8 Oct 2026)

| Source | Endpoint / location | Fields used | Licence / terms | Verified how |
|---|---|---|---|---|
| NASA FIRMS area API | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/{MAP_KEY}/{SOURCE}/{W,S,E,N}/{1..5}/{YYYY-MM-DD}` | latitude, longitude, acq_date, acq_time (UTC, HHMM, leading zeros dropped), satellite (N, N20, N21), confidence (l/n/h), frp (MW), scan, track (km), daynight, bright_ti4, type | NASA open data; acknowledgement required | Live calls; `data_availability` endpoint (SP to 2026-06-30, NRT from 2026-07-01, NOAA-21 NRT from 2024-01-17); `mapkey_status` (5000 transactions / 10 min; ~10 per 5-day area request) |
| Open-Meteo archive | `https://archive-api.open-meteo.com/v1/archive?hourly=wind_speed_10m,wind_direction_10m&wind_speed_unit=ms&timezone=Asia/Kolkata&models=ecmwf_ifs\|era5_land\|era5` | hourly speed (m/s), direction (degrees, FROM) | CC BY 4.0, free for non-commercial use | Live calls for all three models |
| Open-Meteo forecast | `https://api.open-meteo.com/v1/forecast` (`forecast_hours`, `past_days`) | same | same | code path (live alerts) |
| Sentinel-2 L2A | Earth Search STAC `https://earth-search.aws.element84.com/v1`, collection `sentinel-2-l2a`; COGs in `s3://sentinel-cogs` (us-west-2, public) | red (B04), nir08 (B8A), swir16 (B11), swir22 (B12), scl, visual; reflectance = DN × scale + offset from `raster:bands` (0.0001, −0.1) | Copernicus Sentinel data terms: free, "Contains modified Copernicus Sentinel data" | Item metadata inspected; scenes read |
| Copernicus DEM GLO-30 | `s3://copernicus-dem-30m` (public, no requester-pays), `Copernicus_DSM_COG_10_N28_00_E077_00_DEM/...tif` | elevation (m) | Copernicus DEM licence (free with attribution); acquisitions 2011–2015 | Listed and read over HTTPS |
| OpenStreetMap Overpass | `https://overpass-api.de/api/interpreter` (+ mirrors) | `landuse=landfill`, `building=*`, `amenity=school\|college\|kindergarten\|hospital\|clinic`, `railway=station` | ODbL, "© OpenStreetMap contributors" | Live queries; results cached in `cache/` and S3 |
| WorldPop | `https://api.worldpop.org/v1/services/stats?dataset=wpgppop&year=2020&geojson=…` | total_population | CC BY 4.0 | Live calls |
| Amazon Location Service | `geo-places` `Geocode` (Places v2), `Filter.IncludeCountries=["IND"]`, `IntendedUse=SingleUse` | Title, Position, MatchScores | AWS service terms; SingleUse results are not stored (we store none) | Code path; **not yet exercised** (IAM user lacks permission) |
| Protomaps basemap | `https://build.protomaps.com/20261008.pmtiles`, extracted per city with `pmtiles extract` and self-hosted | earth, water, landuse, roads, buildings, boundaries | ODbL (OSM data) | Extracted and rendered |
| News reports | `data/news_fires.csv` | dates, outlet, URL, short quote | links only | Each link opened on 8 Oct 2026 |

Not used: requester-pays buckets, paid APIs, scraping.
