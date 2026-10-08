# Estimated monthly cost (ap-south-1, light hackathon traffic)

| Item | Assumption | Est. USD / month |
|---|---|---|
| Lambda (Watch) | 1,440 executions × 4 tasks × ~3 s × 2 GB | ~0.70 (mostly within free tier) |
| Lambda (Backfill) | 4 runs × ~20 min of task time × 2 GB | ~0.40 |
| Lambda (API) | 20,000 requests × 300 ms × 1 GB | ~0.10 |
| Step Functions (standard) | 1,440 Watch + 4 Backfill executions × ~10 transitions | ~0.40 |
| EventBridge Scheduler | 1,440 invocations | free tier |
| DynamoDB on-demand | < 1 M reads/writes, < 50 MB | ~0.30 |
| S3 | < 1 GB, < 100k requests | ~0.10 |
| ECR | ~1 GB image | ~0.10 |
| SNS email | < 1,000 emails | free tier |
| API Gateway HTTP API | 20,000 requests | ~0.02 |
| Amazon Location (Places Geocode) | 2,000 requests | ~0.10 (check current free tier) |
| Bedrock | 12 briefs × 4 runs × ~1.5k tokens | ~0.30 |
| Amplify Hosting | ~35 MB build, light traffic | ~0.20 |
| CloudWatch | 1 dashboard, 3 alarms, logs < 1 GB | ~3.30 (dashboard $3; delete it after judging) |
| **Total** | | **≈ $6, or ≈ $3 without the dashboard** |

Discipline: no NAT gateway, no provisioned capacity, no GPUs, Map concurrency 1–3, small crops, 90-day expiry on old snapshots, AWS Budgets alert at $5 (`BudgetEmail` parameter). Open data (FIRMS, Open-Meteo, Sentinel-2, DEM) costs nothing to read.
