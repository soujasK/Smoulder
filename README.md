# Smoulder

**India's city landfills catch fire and burn next to homes and schools. Smoulder turns free satellite fire detections and wind records into a dated fire record for each landfill, tells any resident how many days their area was downwind of a detected landfill fire, and emails them when a site lights up and the wind is blowing their way.**

Built for Environmental Hacks (Bharat Builds Tour, WeMakeDevs × AWS Builder Center), Track 01: Air.

| Who | Input | Output |
|---|---|---|
| Resident | an address, landmark or PIN code | **Smoke Days**: "From 2019 to 11 Oct 2026, Bhalaswa was downwind of a detected landfill fire on **10 days**" (MODELLED), with the nearest sites, a calendar and a receipt for every day |
| Resident (subscribed) | email + location (rounded to ~100 m) | **Downwind alert**: "Fire detected at <site> at <time IST>. Wind toward your area for about <h> hours." |
| Journalist, researcher, official | a landfill site | **Fire Record**: detection calendar, fire days per year, episodes, Burn Scan, neighbours, detected vs news-reported days, sources; printable A4 |
| Official | the site list | **Ranking** by fire days × people nearby, with the formula visible |

## What the data says (real numbers, 1 Jan 2019 to 11 Oct 2026)

| Site | City | Area | Fire days (Tier A/B) | Counted detections |
|---|---|---|---|---|
| Dhapa | Kolkata | 61.3 ha | 47 | 83 |
| Kodungaiyur | Chennai | 127.6 ha | 18 | 30 |
| Bhalswa | Delhi | 27.9 ha | 14 | 27 |
| Ghazipur | Delhi | 29.2 ha | 7 | 8 |
| Brahmapuram | Kochi | 24.5 ha (traced) | 7 | 26 |
| Deonar | Mumbai | 127.1 ha | 7 | 12 |
| Perungudi | Chennai | 104.1 ha | 7 | 19 |
| Okhla | Delhi | 25.8 ha | 1 | 1 |
| Kanjur | Mumbai | 142.5 ha | 0 | 0 |
| **9 sites** | **5 cities** | | **108** | **206** |

- 5 of 8 linked news-reported fires have a counted detection within ±1 day (two at Ghazipur, one each at Bhalswa, Brahmapuram and Perungudi; misses at Ghazipur, Okhla and Kodungaiyur are listed in [docs/GATE.md](docs/GATE.md)). 101 of the 108 detected fire days have no report in our (short) list.
- Pirana (Ahmedabad) was evaluated and left out: NASA flags most of its recent detections as a static industrial heat source (FIRMS `type=2`), so they are not fire days. Static sources are never counted at any site.
- Brahmapuram (Kochi), March 2023 fire: Sentinel-2 shows 3.96 ha (1.32–6.60) of burn-like change inside the boundary and 6 hot-surface pixels.
- Perungudi (Chennai), April 2022 fire: Sentinel-2 shows 17.56 ha (10.60–24.52) of burn-like change between clear scenes before and after.
- The numbers are small. Satellites pass about twice a day, pixels are larger than parts of each site, and smouldering below the surface is often invisible. Smoulder shows what was detected and says what it cannot see.

## Run it

```bash
# Python 3.11+ and Node 20+
python -m venv .venv && .venv/Scripts/activate      # or source .venv/bin/activate
python scripts/tasks.py setup                         # pip + npm (or: make setup)
cd web && npm run dev                                 # offline mode on the committed snapshot: http://localhost:5173
```

Offline mode needs no keys and no AWS: `web/public/data/snapshot.json`, terrain tiles, Burn Scan crops and the basemap are committed.

Rebuild the data (needs a free NASA FIRMS MAP_KEY in `.env`, see `.env.example`):

```bash
python scripts/tasks.py gate             # FIRMS backfill + validation gate -> docs/GATE.md
python scripts/tasks.py backfill-local   # + wind, context, Burn Scan, snapshot
python scripts/tasks.py test             # pytest + web type-check + vitest
```

Deploy to AWS (needs an IAM principal allowed to create the stack, and Docker running):

```bash
python scripts/tasks.py preflight        # checks identity, permissions and Docker
python scripts/tasks.py deploy           # SSM key, SAM stack, seed S3, Backfill run, Amplify web app, first Watch run
python scripts/tasks.py replay <det_id>  # re-run the alert path for a real past detection (email says REPLAY)
```

Demo Mode: open `/?demo=1` (scripted, deterministic, uses Bhalaswa metro station, a public landmark).

## Where AWS fits

| Service | Role |
|---|---|
| **AWS Open Data** (S3) | Sentinel-2 L2A COGs (Burn Scan, terrain drape) and Copernicus DEM GLO-30 (3D terrain), read directly from the registry buckets |
| **Step Functions** | `smoulder-backfill`: LoadSites → Map(cities)[FetchFirmsWindows] → Attribute → Map(sites)[Wind, Scenes, Burn Scan, Context] → Validate → GenerateBriefs → PublishSnapshot. `smoulder-watch`: PollNRT → Dedupe → Choice(new?) → Map(detections)[Forecast, DownwindCheck, NotifySNS] → UpdateLiveFeed |
| **EventBridge Scheduler** | starts Watch every 30 minutes |
| **Lambda** (container image) | every pipeline stage and the HTTP API |
| **DynamoDB** | detections, fire days, episodes, context, briefs, subscribers, alerts (idempotency), runs |
| **S3** | raw FIRMS/wind cache, imagery crops, versioned snapshots |
| **SNS** | email alerts with double opt-in; one topic, per-subscriber filter policy |
| **API Gateway** (HTTP API) | `/smoke-days`, `/sites/...`, `/subscribe`, `/live`, `/runs/latest`; IAM-only `/admin/replay` |
| **Amazon Location Service** | Places v2 geocoding, India-filtered, `IntendedUse=SingleUse` (results are not stored) |
| **Amazon Bedrock** | ~100-word briefs from a strict JSON of numbers; every number checked, template fallback |
| **SSM Parameter Store** | FIRMS key (SecureString) |
| **Amplify Hosting** | the web app |
| **CloudWatch** | dashboard (runs, detections, alerts, time to alert, errors), alarms on failures |

Template: [infra/template.yaml](infra/template.yaml) (SAM, passes `cfn-lint`). Cost estimate: [docs/COST.md](docs/COST.md).

## Repository

```
pipeline/   sites, firms, attribute, wind, downwind, context, imagery, terrain, validate, briefs, watch, publish, aws
api/        HTTP API handler
web/        Vite + React + TypeScript + React Three Fiber + MapLibre (self-hosted PMTiles)
config/     every threshold (attribution, downwind, imagery, ranking, terrain, briefs, firms)
data/       news_fires.csv (linked reports used for validation)
infra/      SAM template and Dockerfile
tests/      pytest (parsers, tiers, downwind, alerts, API, briefs, contract); web/src/test (contract, copy lint, DOM receipts)
docs/       ASSUMPTIONS, PROGRESS, GATE, METHOD, DATA_SOURCES, LIMITS, COST, DEMO_SCRIPT, BLOG_DRAFT
```

## AI tools used

This repository was written with **Claude Code (Anthropic, Claude Opus 5.5)** working from a written specification by the team. The team reviewed the decisions recorded in `docs/ASSUMPTIONS.md`. Briefs in the product are generated at run time by Amazon Bedrock, number-checked, and labelled "Generated draft".

## Credits

NASA FIRMS (VIIRS 375 m active fire); Open-Meteo (ECMWF IFS, ERA5, ERA5-Land; CC BY 4.0); Copernicus Sentinel-2 and Copernicus DEM via the AWS Open Data registry ("Contains modified Copernicus Sentinel data"); © OpenStreetMap contributors (ODbL); WorldPop (CC BY 4.0); Protomaps basemap. See [CREDITS.md](CREDITS.md).

## Prior work disclosure

No code existed before this build; all code was written during the hackathon following the kickoff on 8 Oct 2026. The idea draws on published work on satellite waste-fire surveillance (see the Method page); Smoulder is a public, per-site, per-address record and alert, not a new detection method.

## Licence

MIT. Data remains under its own licences (see CREDITS.md).
