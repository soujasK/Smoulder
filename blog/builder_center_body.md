**TL;DR:** NASA satellites see landfill fires in Indian cities every year, but nobody tells the people living downwind. **Smoulder** turns those detections plus hourly wind into one answer for any address: *how many days was this place downwind of a burning landfill?* It runs serverless on AWS for about $3–6 a month.

---

## The problem

There's a school in Delhi a few metres from the Bhalswa landfill. When the landfill burns, a satellite logs the fire and the detection lands in a public NASA dataset by morning.

The parents never find out. The data exists, but nobody turns it into the one question a family would ask:

> **"On how many days was my street downwind of a burning landfill?"**

---

## What Smoulder does

Type a place, get a number.

- **Kharki, Kolkata** (beside the Dhapa landfill): **34 smoke days**
- **Bhalswa Jahangirpuri, Delhi**: **12 smoke days**

Every day comes with a receipt: which satellite saw the fire, when, and which way the wind blew, hour by hour. Residents can also subscribe to an email alert when a new fire's smoke is heading their way.

---

## Why you can trust the number

Getting *a* number was easy. Getting one we'd defend took three strict rules.

**1. The pixel is bigger than the dump.** A satellite fire pixel at Bhalswa covers about **30 ha**; the whole landfill is about **28 ha**. So we only count a detection if the pixel lands on or overlaps the landfill boundary. Nearby fires are shown but never counted.

**2. Some "fires" are factories.** At Pirana (Ahmedabad), NASA flagged most detections as a *static industrial heat source*. We dropped the site, and our headline went from **311 fire days to 108**. We'd rather publish 108 we can defend than 311 we can't.

**3. Every number says what it is.** Satellite detections are labelled **MEASURED**; smoke days are **MODELLED**. The wind rule is one sentence: *downwind within ±30°, at least 1 m/s, for at least an hour in the six hours after the fire.*

---

## What the data shows

- **108 fire days** detected across **9 landfills in 5 cities**
- **101** of them had **no news report** we could find
- **~12 lakh people** live within 1 km of these sites, including **1.6 lakh people and 13 schools** around Bhalswa alone

We checked ourselves against the news too: satellites caught **3 of 5** reported Delhi fires, and Sentinel-2 imagery confirmed about **17.6 ha** of burn-like change after a major fire at Chennai's Perungudi dumpsite.

---

## How it's built on AWS

```
NASA fire data · wind · Sentinel-2 (AWS Open Data)
        │
EventBridge (every 30 min) → Step Functions → Lambda → S3 + DynamoDB
        │                                          │
   SNS email alerts                     API Gateway → Amplify web app
```

- **EventBridge Scheduler + Step Functions** run a *Watch* every 30 minutes: poll NASA for new fires, check the wind forecast, and alert subscribers via **Amazon SNS**.
- A second Step Functions *Backfill* rebuilds the full record on **Lambda** (one container image, 19 stages) and stores it in **S3** and **DynamoDB**.
- **Sentinel-2** and elevation data are read in place from the **AWS Open Data registry**; we never download a scene.
- **Amazon Location** turns addresses into points without storing them; **API Gateway** and **Amplify** serve the app.

Two design choices worth stealing:

```yaml
FetchCities:
  Type: Map
  MaxConcurrency: 1   # NASA's rate limit, enforced by the architecture itself
```

- **Rate limits in the architecture**, not in retry loops: the city loop can't exceed NASA's quota, and every response is cached in S3.
- **Alerts can't double-send:** each (subscriber, fire) pair is claimed with a conditional DynamoDB write before SNS sends anything.

---

## An AI that can't invent numbers

**Amazon Bedrock** drafts a short plain-language brief for each landfill, but it only gets a JSON of facts, and every number in its output is checked against that JSON. If a single number doesn't match, the draft is rejected and a template written from the same facts is shown instead. The model writes the prose; it never supplies the facts.

---

## What we learned

1. **Start from a person's question**, not from the dataset.
2. **Decide what not to count**, and write the reason down.
3. **Label evidence honestly:** measured and modelled shouldn't look the same.
4. **Put limits into the architecture**, not into error handling.
5. **Wrap generative AI in checks you can show.**

---

**Try it with your own place:** [main.d1qmqrr59i747k.amplifyapp.com](https://main.d1qmqrr59i747k.amplifyapp.com)
**Code:** [github.com/soujasK/Smoulder](https://github.com/soujasK/Smoulder)

*Data: NASA FIRMS · Open-Meteo · Copernicus Sentinel-2 and DEM (AWS Open Data) · © OpenStreetMap contributors · WorldPop*
