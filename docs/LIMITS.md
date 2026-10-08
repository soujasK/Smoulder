# Limits (shown in the app as "What this does not show")

1. **No emissions, tonnes burned or health effects.** Smoulder counts detections and models wind direction. It never says anyone was exposed.
2. **Smouldering below the surface is often invisible.** VIIRS sees hot pixels at overpass time; deep-seated landfill fires can burn for weeks without a detection.
3. **Pixels are larger than the site.** A VIIRS pixel is about 375 m at nadir (14 ha) and up to about 800 m off-nadir; our sites are 25–140 ha. Tier B detections can include fires just outside the boundary. Tier C detections (within 2 km, no overlap) are shown but never counted.
4. **Two overpasses a day per satellite** (about 01:30 and 13:30 local). Short fires between passes are missed.
5. **Cloud and smoke** hide fires from VIIRS and hide the ground from Sentinel-2. Many episodes have no clear scene.
6. **OSM coverage gaps.** Counts are of mapped features. The Brahmapuram boundary had to be traced by hand because OSM maps only the plant.
7. **Modelled wind** (9 km ECMWF IFS, else 0.1° ERA5-Land, else 0.25° ERA5) cannot resolve street-level flow, buildings or the real plume. Smoke Days is a count of hours the model wind pointed at a place.
8. **Burn Scan measures burn-like surface change** (dNBR > 0.27). Fresh dumping, earthworks, wetness and haze also change a landfill's surface.
9. **The DEM is a surface model from 2011–2015.** Landfill heights today differ; buildings add relief.
10. **The news list is short** (6 linked reports). A detected fire day without a report in our list may well have been reported elsewhere.
11. **Population** is a 2020 gridded estimate, not a census.
