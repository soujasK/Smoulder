# A satellite pixel is bigger than the dump

### How we gave landfill smoke a street address, using open data and AWS

There's a school in north Delhi that sits a few metres from the Bhalswa landfill. On some nights the landfill catches fire. Satellites roughly 800 km up pass overhead, notice a hot pixel and log it. By morning that detection is in a public NASA dataset anyone can download.

The parents at that school never find out.

The data exists and the fires are real, but the two have never been connected to the one question a family would actually ask: **"On how many days was my street downwind of a burning landfill?"**

We built **Smoulder** to answer that question for any address near nine landfills in five Indian cities. Here's what we learned, most of which surprised us.

---

## The question an AQI app can't answer

Air-quality apps tell you the air is bad today. They can't tell you *why*, or whether a specific fire upwind of you was the reason. Landfill fires are a peculiar pollution source: frequent, local, often at night, and mostly invisible in city-wide averages.

So we flipped the usual dashboard around. Instead of "what's the AQI?", Smoulder asks one thing:

> Type a place. Get the number of days it was downwind of a detected landfill fire, with a receipt for every day.

Type **Kharki, Kolkata**, a village beside the Dhapa landfill, and the answer is **34 smoke days** over seven years of satellite records. That's more than a month. Type **Bhalswa Jahangirpuri, Delhi** and you get **12**, each with the satellite pass, the time, and the wind hour by hour.

---

## Three things satellites don't tell you

Getting that number was easy. Getting a number we'd stand behind took most of the work.

### 1. The pixel is bigger than the dump

NASA's VIIRS sensors detect fire in pixels of about 375 m at the centre of the swath, and those pixels grow toward the edge. At Bhalswa, one pixel covers about **30 hectares**, while **the whole landfill is about 28**.

So a "fire at Bhalswa" might be a fire *next to* Bhalswa. We sort every detection into three tiers:

- **Tier A**: the pixel centre falls inside the landfill boundary. Counted.
- **Tier B**: the pixel footprint overlaps the boundary. Counted.
- **Tier C**: nearby, but no overlap. **Shown, never counted.**

Around Bhalswa there are hundreds of Tier C detections from an industrial area about a kilometre away. A naive "fires within 2 km" filter would have attributed all of them to the dump.

### 2. A detection is not a measurement of how much burned

A detection says *a pixel was hot when the satellite passed*. It says nothing about acres burned or smoke produced. Every number in Smoulder carries a label saying what kind of evidence it is: **MEASURED** (an instrument saw it), **COUNTED** (mapped features), **ESTIMATED** (gridded population), **MODELLED** (our wind rule), or **COMPILED** (linked news reports). Smoke days are always labelled MODELLED, because they are.

### 3. Some "fires" aren't fires

We added Pirana in Ahmedabad, one of India's oldest dumpsites, and the numbers exploded to hundreds of fire days. Then we looked closer.

NASA tags each archived detection with a type, and most of Pirana's recent detections were **type 2: "other static land source"**: persistent industrial heat, not a fire event. The detections NASA *hadn't* flagged sat on the same spot.

We could have kept Pirana and published a dramatic number. Instead we made NASA's static flag a hard rule (never counted, at any site) and **left Pirana out of the record**, with the reasoning written down in our assumptions file. That one decision cut our headline from 311 fire days to 108. We'd rather publish 108 we can defend than 311 we can't.

---

## The wind is the missing link

A fire only matters to you if its smoke comes your way. For every detected fire day, Smoulder pulls hourly 10 m wind from Open-Meteo (ECMWF and ERA5 models) and applies one transparent rule:

> A place has a **smoke day** if, in the six hours after the first counted detection at a landfill within 5 km, the wind blew from the landfill toward it (within ±30°, at least 1 m/s) for at least one hour.

Calm hours are counted separately and never as downwind, because wind direction is meaningless in still air. The rule fits in one sentence on the Method page, and anyone can check it against the per-day receipts.

---

## What the record shows

Across **9 landfills in 5 cities**, satellites detected **108 fire days**. We compiled a list of news reports about these fires, and **101 of the 108 detected fire days had no report we could find.** That isn't proof nobody reported them, but it shows how little of this ends up on the record.

About **12 lakh people** live within a kilometre of these nine sites. Around Bhalswa alone that's **1.6 lakh people and 13 schools**.

We also checked ourselves against the news. For Delhi, satellites caught **3 of 5** reported landfill fires within a day. The misses stay in the table: satellites pass about twice a day per satellite, and short or smouldering fires slip between passes. For a major fire at Chennai's Perungudi dumpsite, an independent check using **Sentinel-2 imagery from the AWS Open Data registry** showed about **17.6 hectares** of burn-like change between clear scenes before and after. That's a second instrument agreeing with the first.

---

## How it runs on AWS

Smoulder is two Step Functions state machines and a small API, deployed with AWS SAM in the Mumbai region.

```
EventBridge Scheduler (every 30 min)
        │
        ▼
Step Functions: WATCH ──► PollNRT → Dedupe → (new fire?) → Map[ForecastWind → DownwindCheck → SNS] → UpdateLiveFeed
Step Functions: BACKFILL ► LoadSites → Map(cities)[FetchFIRMS] → Attribute → Map(sites)[Wind · BurnScan · Context]
                           → Validate → GenerateBriefs → PublishSnapshot
        │
        ▼
Lambda (one container image) ──► S3 (raw cache, imagery, snapshots) · DynamoDB (record, subscribers, alerts)
        │
        ▼
API Gateway HTTP API + Lambda ──► Amplify-hosted web app        Amazon Location (geocoding) · Amazon SNS (alerts)
```

A few choices we're glad we made:

- **Rate limits are designed in, not handled as errors.** NASA's FIRMS API has a transaction quota, so the Backfill's city loop is a Step Functions `Map` with `MaxConcurrency: 1`. The pipeline physically can't exceed the quota, and every raw window is cached in S3, so a re-run costs almost nothing.
- **One container image, many tasks.** The geospatial stack (rasterio, shapely, pyproj) is too heavy for a zip, so every stage runs from one Lambda container image with a `task` field choosing the work. Nineteen Backfill stages, one artifact to build.
- **Read open data in place.** Sentinel-2 imagery and the Copernicus elevation model come straight from the **AWS Open Data registry** as cloud-optimised GeoTIFFs. We read only the pixel windows around each landfill and never download a scene.
- **Alerts that can't double-send.** Each subscriber gets an SNS filter policy keyed to their own ID, and every (subscriber, detection) pair is claimed with a conditional DynamoDB write (`attribute_not_exists`) before anything is sent. A retry or a re-run can't email anyone twice.
- **Privacy by construction.** Amazon Location geocodes addresses with `IntendedUse=SingleUse`, so results aren't stored. Subscriber locations are rounded to about 100 m, and our own tables keep only a hash of each email (SNS holds the address it delivers to).
- **It costs less than a coffee.** Our estimate is about **$3–6 a month**, most of it a CloudWatch dashboard we can switch off. No NAT gateway, no provisioned capacity, nothing idle.

The live Pipeline page reads real runs back from DynamoDB: a Watch every thirty minutes, finishing in about 26 seconds, and a full 19-stage Backfill in about six minutes.

---

## An AI that isn't allowed to invent numbers

Each landfill gets a ~100-word plain-language brief drafted by **Amazon Bedrock**. Language models are fluent and confidently wrong with numbers, and in a record like this one invented number would undo everything else.

So the model never sees raw data. It gets a strict JSON of facts, and the prompt says:

> *Use only the numbers in the JSON you are given, written exactly as given (no rounding, no new numbers, no percentages, no arithmetic).*

Then we **check every number in the output** against the JSON, and lint for loaded words like "toxic" or "illegal" that a factual record shouldn't use. A failing draft gets one retry with the exact problems listed. If it still fails, or the model isn't available, the page shows a deterministic template written from the same facts.

That fallback isn't hypothetical: the template is what our first live run served. The page labels which one you're reading.

---

## Three bugs that taught us something

1. **The Docker build that never finished.** Our SAM template builds the Lambda image from the repository root, and without a `.dockerignore` Docker tried to upload gigabytes of cached satellite data and `node_modules` as build context. A six-line whitelist cut it to about 650 KB.
2. **The map that only broke in production.** MapLibre loads its web worker relative to its own module. In development that works; once the bundler inlines the library, the path points nowhere. We now ship the worker as an explicit asset, and taught Amplify's rewrite rules that `.mjs` is a real file, not a route.
3. **The geocoder that was too helpful.** In our scripted demo, typing "Bhalaswa" (a metro station) went to the geocoder, which picked a different Bhalswa a kilometre away and returned 1 day instead of 10. Curated public landmarks now resolve to their own exact point before any geocoding happens.

---

## Designing for a calm reading

A record about fires near schools shouldn't look like an emergency. Smoulder's interface is deliberately quiet: a pale "morning haze" palette, haze blue for anything about air and wind, ember orange **only** for fire, and plain sentences. Every number has a receipt one click away. It works on a phone and in Hindi, and any record prints as a sourced A4 sheet you can take to a ward office.

---

## What it doesn't show

We put this on the Method page, so it belongs here too:

- **No emissions, no tonnes burned, no health effects.** Smoke days are a modelled downwind count, not a measure of what anyone breathed.
- **Satellites miss things.** Smouldering below the surface, fires between passes, and fires under cloud or thick smoke. Our counts are a floor, not a total.
- **Coverage is nine sites.** Adding a landfill is one config entry and a pipeline run; the method doesn't change.

---

## What we'd do next

The same pipeline works for any open burning a satellite can see. Crop-residue fires upwind of a city and industrial sites near schools are both the same three steps: **attribute the pixel, apply the wind, count the days at an address.**

India has thousands of dumpsites, and most have never been mapped, let alone given a public fire record. Smoulder shows it can be done with open data, a few serverless pieces, and a strict rule about what counts as evidence.

---

**Try it:** [main.d1qmqrr59i747k.amplifyapp.com](https://main.d1qmqrr59i747k.amplifyapp.com) · **Code:** [github.com/soujasK/Smoulder](https://github.com/soujasK/Smoulder)

*Data: NASA FIRMS (VIIRS); Open-Meteo (ECMWF IFS, ERA5); Copernicus Sentinel-2 and Copernicus DEM via the AWS Open Data registry; © OpenStreetMap contributors; WorldPop (CC BY 4.0).*
