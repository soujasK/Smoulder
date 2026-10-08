# Demo video script (3:00)

Record at 1920×1080, browser at 100 % zoom, cursor hidden in Demo Mode. Voice: calm, factual, no adjectives about the fires. Every number below comes from the snapshot of 8 Oct 2026; re-read them from the app on recording day.

| Time | Shot | Voice-over |
|---|---|---|
| 0:00–0:07 | `/?demo=1`. Night screen; Delhi contour plate from the Copernicus DEM; the question types in (1.2–4.2 s). | "Delhi's landfills catch fire, next to homes and schools. Nobody keeps a record a resident can use." |
| 0:07–0:22 | The landmark "Bhalaswa" types in (4.8–6.4 s), submit at 7.0 s; the camera descends to Bhalswa; the date ticker runs 2019 → 2026 (~18 s); ember columns rise on their real dates; wind wedges swing out; the counter reaches **10**. | "Smoulder checked every satellite fire detection at Bhalswa since 2019, and the wind each time. Bhalaswa station was downwind on ten days. Modelled, with a receipt for every day." |
| 0:22–0:45 | Scroll: nearest sites, calendar, per-day receipts; then the Sites page (ledger). | "Three users. A resident types a place and gets Smoke Days. A journalist opens a site and gets its fire record. An official gets a ranking with the formula on screen." |
| 0:45–1:05 | `/site/bhalswa?pixel=A`, then Tier B, then Tier C. | "Why trust it? One satellite pixel here is about thirty hectares, about the size of the whole site. Centre inside the boundary: Tier A. Overlapping: Tier B. Nearby only: Tier C, shown and never counted. Three hundred Tier C detections near Bhalswa are an industrial area a kilometre south, not the dump." |
| 1:05–1:30 | `/site/brahmapuram`: calendar with the news tick in March 2023; Burn Scan scan-line reveal; pre/post slider. | "Kochi, March 2023. The fire was in the news; the satellite saw it on 3, 4 and 5 March. Sentinel-2 shows about four hectares of burn-like change inside the boundary, with a range, because pixels at the edge are uncertain. Across nine sites in five cities, a hundred and one of a hundred and eight detected fire days have no news report we could find." |
| 1:30–1:55 | Split screen: Subscribe on the app; terminal `python scripts/tasks.py replay e66cc4ca1aec`; phone receives the SNS email titled "REPLAY of detection from 27 Apr 2022…"; `/pipeline` time-to-alert row. | "Residents subscribe with an email. When a site lights up and the forecast wind blows their way, Amazon SNS sends an alert. This is a labelled replay of a real detection with its real wind. Time from first seen to alert: <read from the Pipeline page>." |
| 1:55–2:10 | Phone (360 px), EN → हिं, Smoke Days in Hindi; then Print record → A4 preview. | "It works on a phone, in Hindi. And any record prints as a sourced A4 sheet." |
| 2:10–2:45 | `/pipeline` (runs animate); AWS console: EventBridge schedule; Step Functions graphs (Backfill, Watch); SNS topic; DynamoDB items; S3 open data (sentinel-cogs, copernicus-dem-30m); Amazon Location; Bedrock brief; Amplify URL. | "All of it runs on AWS. EventBridge starts the watch every thirty minutes. Step Functions runs backfill and watch on Lambda. Sentinel-2 and the Copernicus elevation model come straight from the AWS Open Data registry. DynamoDB holds the record, SNS sends alerts, Amazon Location finds addresses, Bedrock drafts briefs that are number-checked, and Amplify serves the app." |
| 2:45–3:00 | Back to the Method page: tiers; "What this does not show". | "Measured where we can, modelled where we must, and labelled every time. Satellites miss smouldering fires, so these numbers are a floor. Next: every city that keeps a landfill." |

## Demo Mode timings (`web/src/demo/script.ts`)
- 0 ms: wide view of Delhi from the south (44 km).
- 1,200–4,200 ms: question types in.
- 4,400 ms: camera eases to 26 km.
- 4,800–6,400 ms: "Bhalaswa" types into the input.
- 7,000 ms: submit; the answer camera takes over (distance = max(9 km, 4 × station distance)).
- 7,600–~25,000 ms: span 2019 → data date plays (11 s × 1.6); counter increments to the real number.

## Before recording
- Run `python scripts/tasks.py deploy` with permitted credentials, subscribe your own email and confirm it, then run the replay once to check delivery.
- Re-read the numbers above in the app (the snapshot may have changed).
- The landmark is a public station. Never show a private address.
