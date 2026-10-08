# Day-1 gate

Generated 2026-10-11 by `python -m pipeline.validate.gate` from real FIRMS data (no fixtures).

**Result: PASS.** Delhi news events with a counted (Tier A/B) detection within ±1 day: 3 of 5 (60%). Threshold: 50%.

## Events

| Site | Reported | Outlet | Hit | Counted detections | Detection dates (IST) | Max FRP (MW) |
|---|---|---|---|---|---|---|
| ghazipur | 2022-03-28 to 2022-03-30 | [Scroll.in](https://scroll.in/latest/1020586/delhi-fire-breaks-out-at-ghazipur-landfill-no-casualty-reported) | hit | 2 | 2022-03-29 | 1.68 |
| ghazipur | 2022-04-09 to 2022-04-10 | [Scroll.in](https://scroll.in/latest/1021523/delhi-fire-breaks-out-again-at-ghazipur-landfill-no-casualties-reported) | miss | 0 | - | - |
| bhalswa | 2022-04-26 to 2022-04-29 | [Down To Earth](https://www.downtoearth.org.in/blog/waste/third-dumpsite-fire-in-a-month-points-to-systemic-failure-of-waste-management-in-delhi-82618) | hit | 4 | 2022-04-27 | 6.47 |
| ghazipur | 2024-04-21 to 2024-04-22 | [Wikipedia](https://en.wikipedia.org/wiki/Ghazipur_landfill) | hit | 1 | 2024-04-22 | 3.78 |
| okhla | 2025-02-07 | [The Tribune](https://www.tribuneindia.com/news/delhi/fire-erupts-at-okhla-landfill) | miss | 0 | - | - |
| brahmapuram | 2023-03-02 to 2023-03-13 | [Onmanorama](https://www.onmanorama.com/news/kerala/2023/03/14/brahmapuram-fire-waste-dumping-yard-kochi.amp.html) | hit | 18 | 2023-03-03, 2023-03-04, 2023-03-05 | 8.23 |
| perungudi | 2022-04-27 to 2022-04-28 | [Scroll.in](https://scroll.in/latest/1022851/chennai-firefighters-struggle-to-douse-perungudi-landfill-blaze) | hit | 7 | 2022-04-28 | 8.77 |
| kodungaiyur | 2022-05-20 to 2022-05-21 | [The News Minute](https://www.thenewsminute.com/tamil-nadu/major-fire-chennai-s-kodungaiyur-dump-yard-weeks-after-perungudi-blaze-164215) | miss | 0 | - | - |

## Detections by tier

| Site | Tier A | Tier B | Tier C (not counted) |
|---|---|---|---|
| bhalswa | 8 | 20 | 308 |
| brahmapuram | 15 | 14 | 603 |
| deonar | 11 | 10 | 14 |
| dhapa | 83 | 22 | 18 |
| ghazipur | 4 | 4 | 10 |
| kanjur | 0 | 0 | 17 |
| kodungaiyur | 28 | 6 | 22 |
| okhla | 0 | 2 | 19 |
| perungudi | 14 | 5 | 7 |

## Fire days per year (counted A/B, nominal/high confidence)

| Site | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| bhalswa | 2 | 1 | 1 | 5 | 1 | 2 | 1 | 1 |
| brahmapuram | 1 | 1 | 1 | 1 | 3 | 0 | 0 | 0 |
| deonar | 2 | 2 | 2 | 0 | 1 | 0 | 0 | 0 |
| dhapa | 1 | 12 | 10 | 6 | 0 | 5 | 9 | 4 |
| ghazipur | 1 | 0 | 1 | 1 | 1 | 3 | 0 | 0 |
| kanjur | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| kodungaiyur | 1 | 5 | 3 | 4 | 1 | 0 | 0 | 4 |
| okhla | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| perungudi | 0 | 1 | 0 | 1 | 0 | 3 | 2 | 0 |

Detected fire days with no news report in the compiled list: 101 (the list is short; this is not a claim that those fires went unreported).

## Inputs

- Sources: VIIRS_NOAA20_NRT, VIIRS_NOAA20_SP, VIIRS_SNPP_NRT, VIIRS_SNPP_SP; availability {"VIIRS_NOAA20_NRT": ["2026-07-01", "2026-10-11"], "VIIRS_NOAA20_SP": ["2018-04-01", "2026-06-30"], "VIIRS_SNPP_NRT": ["2026-07-01", "2026-10-11"], "VIIRS_SNPP_SP": ["2012-01-20", "2026-06-30"]}
- City bboxes (W,S,E,N): {"delhi": [77.1029, 28.4623, 77.3821, 28.7889], "kochi": [76.3238, 9.9406, 76.4246, 10.0395], "mumbai": [72.874, 19.0135, 73.0085, 19.1734], "chennai": [80.1733, 12.9048, 80.3224, 13.1867], "kolkata": [88.3703, 22.4856, 88.4796, 22.5883]}
- Raw detections after dedupe: 5755; attributed to a site (A/B/C): 1264
- News list: `data/news_fires.csv` (each row links to its source).

## Caveats

- VIIRS pixels (~375 m) are larger than half of each site; Tier B can include fires just outside the boundary.
- Overpasses are about twice a day per satellite; short fires between overpasses are missed. Cloud and smoke can hide fires.
- Reported dates are when news said the fire began; night overpasses after midnight IST fall on the next date, hence ±1 day.
