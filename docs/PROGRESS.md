# Progress (8 Oct 2026)

## Done
- **M1 Gate: PASS.** 3 of 5 Delhi news events have a counted detection within ±1 day (`docs/GATE.md`). All cities: 4 of 6.
- **M2 Core data:** 6 sites (Brahmapuram traced); FIRMS 2019 → today (2,276 requests, cached); attribution A/B/C; fire days and episodes; Open-Meteo wind per fire day; downwind sectors; Smoke Days for 21 public stations; OSM + WorldPop context; ranking; schools downwind; snapshot + Pydantic/TS contract.
- **M3 Offline web:** Smoke Days (with "All years"), Atlas (MapLibre on self-hosted PMTiles; plan fallback without WebGL), Fire Record, Method, Pipeline, A4 print sheets, Hindi UI, Demo Mode.
- **M4 3D:** Copernicus DEM terrain with contour shader, Sentinel-2 drape, ember columns (shader-animated), wind wedges, pixel-truth footprints, graticule, scale bar, north arrow, VE label; still-image fallback for no WebGL / reduced motion.
- **M5–M7 code (not deployed):** SAM template (S3, 11 DynamoDB tables, container Lambdas, Backfill and Watch state machines, EventBridge Scheduler, SNS, HTTP API with IAM-only replay, CloudWatch dashboard and alarms, Budget); Step Functions task handlers; Watch/alert path with idempotency and REPLAY labelling; HTTP API (Amazon Location geocoding, no persistence); Bedrock briefs with number check and template fallback; Burn Scan (dNBR, hot-surface heuristic, crops).
- **Tests:** 43 pytest (parsers, UTC→IST, tiers at boundaries, low confidence, gap rule, downwind at ±30°, calm, R cutoff, date-only fallback, validation, alerts idempotent/REPLAY/not-downwind, API smoke-days matches precompute and writes nothing, rate limit, briefs number check and banned words, contract); 11 vitest (schema contract, copy lint EN/HI/briefs/JSX, every `[data-metric]` has tier + receipt, "no detections" years). 360 px: no horizontal scroll on Home, Sites, Site, Method, Pipeline (Playwright). `cfn-lint` clean.

## Not done
- **Deployed 11 Oct 2026 (ap-south-1).** Web: https://main.d1qmqrr59i747k.amplifyapp.com · API: https://dx9z3hlgxb.execute-api.ap-south-1.amazonaws.com. Cloud Backfill `backfill-20261011T104926Z` SUCCEEDED and published 9 sites / 108 fire days (matches the local run); first Watch SUCCEEDED; EventBridge runs Watch every 30 min. Verified live: Amazon Location geocoding (/smoke-days for Jahangirpuri and Velachery), CORS locked to the Amplify origin, IAM-only /admin/replay returns 403 unsigned. Fixes found on the way: .dockerignore (build context was GBs), Dockerfile path, HttpApi IAM authorizer, MapLibre worker missing from production builds, Amplify rewrite for .mjs. Not yet exercised: SNS email confirmation and a real alert (needs a subscriber), Bedrock briefs (model access not enabled; template briefs are served).
- **Sites 7–9 added 11 Oct 2026:** Perungudi, Kodungaiyur (Chennai), Dhapa (Kolkata). Pirana (Ahmedabad) evaluated and left out (static heat source). FIRMS `type=2` static sources are no longer counted. See docs/ASSUMPTIONS.md §25–29.
- No live URL yet, no real alert email yet, no recorded video.
- Hindi strings and Hindi template briefs need a native speaker's review.

## Known issues
- The Atlas ranks only one site (Bhalswa): the others had no counted detection in the last 365 days.
- Overpass is often overloaded; context and landmarks are cached (`cache/raw`, seeded to S3 on deploy).
- React dev warning "synchronously unmount a root" from drei `<Html>` under StrictMode (dev only).
- Main JS chunk is 1.45 MB (three.js); routes are code-split.

## Stubs
None. Offline Smoke Days is limited to precomputed public stations and says so ("offline · precomputed").

## Human verification list
1. News events and links in `data/news_fires.csv` (6 rows, opened 8 Oct 2026). The Brahmapuram Feb 2025 seed was dropped: no working link found.
2. FIRMS field meanings (scan/track in km, acq_time UTC HHMM, confidence l/n/h) against the VIIRS attribute table.
3. Wind models: ECMWF IFS used for almost all hours (per-hour model in the snapshot); check Open-Meteo terms and attribution.
4. DEM vintage (2011–2015) and the Copernicus DEM licence text in CREDITS.md.
5. WorldPop 2020 `wpgppop` licence (CC BY 4.0) and citation.
6. Amazon Location Places v2 terms for `IntendedUse=SingleUse`.
7. Prior work: confirm the 2026 *Waste Management* and 2024 *Science of the Total Environment* papers (full citations), and re-run the "no public per-site, per-address record" search.
8. Hindi text (UI and briefs).
9. Bedrock model access in ap-south-1 for `apac.anthropic.claude-sonnet-4-20250514-v1:0` (or set `BedrockModelId`).
10. Site polygons, especially the traced Brahmapuram boundary and the Deonar/Kanjur OSM polygons.
