# How many days was your area downwind of a burning landfill? Building Smoulder on AWS

*Draft for AWS Builder Center. Numbers are from the snapshot of 8 Oct 2026.*

Delhi's Ghazipur, Bhalswa and Okhla landfills, Mumbai's Deonar and Kanjur, Kochi's Brahmapuram, Chennai's Perungudi and Kodungaiyur, and Kolkata's Dhapa sit next to homes and schools. Their fires are reported one at a time, in the news. We wanted a record a resident could use: type a place, get a number, and get a warning when smoke is heading your way.

## The idea in one input and one output
You type an address, landmark or PIN code. Smoulder answers: "From 2019 to 8 Oct 2026, Bhalaswa was downwind of a detected landfill fire on 10 days." The number is modelled, not measured, and the app says so with a MODELLED tag. Every day behind it has a receipt: which site, how many satellite detections, the hours the wind blew toward you, and which weather model said so.

## Data, all open
- **NASA FIRMS** VIIRS 375 m detections, 2019 onward.
- **Open-Meteo** hourly wind (ECMWF IFS 9 km, ERA5-Land, ERA5).
- **Sentinel-2 L2A** and the **Copernicus DEM**, read directly from the **AWS Open Data registry**, for the Burn Scan and the 3D terrain.
- **OpenStreetMap** and **WorldPop** for what is nearby.

## Honesty is a feature
A VIIRS pixel is about as big as Bhalswa itself. So each detection gets a tier: A (pixel centre inside the boundary), B (pixel overlaps) or C (nearby only, never counted). Tier C caught about 300 night-time detections a kilometre south of Bhalswa, in an industrial area. Counting those would have multiplied the detections at Bhalswa more than tenfold (307 Tier C against 28 counted). At Brahmapuram, OSM mapped only the plant, so the March 2023 fire showed up as Tier C until we traced the real dump boundary from Sentinel-2. With the corrected boundary, the fire is counted on 3–5 March, and Sentinel-2 shows about 4 ha of burn-like change.

## Architecture
EventBridge Scheduler → Step Functions (Watch) every 30 minutes: poll FIRMS, attribute, de-duplicate in DynamoDB, fetch the forecast, run the downwind rule per subscriber, send email with SNS. A second state machine (Backfill) rebuilds the record: Lambda container tasks fetch FIRMS, wind, Sentinel-2 and context, validate against news reports, ask Bedrock for briefs whose every number is checked against the data, and publish a versioned snapshot to S3. API Gateway and Lambda serve Smoke Days, with Amazon Location Service for geocoding (single-use; nothing stored). Amplify hosts the React Three Fiber app.

## What we learned
- Satellite detections of landfill fires are sparse: 108 fire days across nine sites in five cities in nearly eight years, and 101 of them have no news report in our list. We show "no detections" rather than zero-filled charts.
- Validate early. Our day-1 gate (3 of 5 Delhi news events detected) decided whether to build at all.
- Put every threshold in config and every number next to its source.

*AI tools: built with Claude Code (Anthropic).*
