import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useSnapshot } from '../data/snapshot';
import { TierChip } from '../components/Tier';
import { Limits } from '../components/Limits';
import { dateLabel } from '../lib/format';
import './method.css';

export function Method() {
  const snap = useSnapshot();
  const loc = useLocation();
  useEffect(() => {
    if (loc.hash) document.getElementById(loc.hash.slice(1))?.scrollIntoView();
  }, [loc.hash, snap.data]);
  const d = snap.data;
  if (!d) return null;
  const a = d.parameters.attribution as Record<string, number | string | boolean>;
  const w = d.parameters.downwind as Record<string, number>;
  const f = d.parameters.firms as Record<string, unknown>;
  const v = d.validation;
  return (
    <main id="main" className="method page">
      <header className="method-head">
        <p className="label">Method · run {d.pipeline_run_id} · data through {d.data_through}</p>
        <h1 className="serif">How every number is made</h1>
        <p className="lede serif">Smoulder turns free satellite fire detections and modelled wind into a dated record per landfill site, and a modelled count of days an address was downwind of a detected fire. Each number below carries a tier: what kind of evidence it is.</p>
      </header>

      <nav className="toc" aria-label="Contents">
        <ol>
          {['Tiers', 'Sites', 'Detections', 'Attribution', 'Smoke Days', 'Context', 'Burn Scan', 'Validation', 'Briefs', 'Alerts', 'Sources', 'Prior work', 'Limits', 'Reproduce'].map((x, i) => (
            <li key={x}><a href={`#${x.toLowerCase().replace(/ /g, '-')}`}><span className="mono">{String(i + 1).padStart(2, '0')}</span> {x}</a></li>
          ))}
        </ol>
      </nav>

      <Sec id="tiers" n={1} title="Tiers">
        <dl className="tiers">
          <dt><TierChip tier="MEASURED" /></dt><dd>Observed by an instrument: a satellite detection, a Sentinel-2 reflectance, a system log timestamp.</dd>
          <dt><TierChip tier="COUNTED" /></dt><dd>A count of features mapped in OpenStreetMap. Coverage varies; a count is a lower bound of what exists.</dd>
          <dt><TierChip tier="ESTIMATED" /></dt><dd>A gridded statistical estimate (WorldPop population, 2020).</dd>
          <dt><TierChip tier="MODELLED" /></dt><dd>Computed from a model and a rule (downwind from reanalysis/forecast wind). Not an observation of smoke and not exposure.</dd>
          <dt><TierChip tier="COMPILED" /></dt><dd>Collected from linked news reports. A reference, not ground truth.</dd>
        </dl>
      </Sec>

      <Sec id="sites" n={2} title="Sites">
        <p>Nine sites in five cities (Delhi, Mumbai, Kochi, Chennai, Kolkata). Boundaries are OpenStreetMap <code>landuse=landfill</code> polygons, except Brahmapuram, where OSM maps only the 6.5 ha plant: its waste surface was traced by hand on a Sentinel-2 true-colour scene and cross-checked against the March 2023 fire detections (<code>boundary_source: traced</code>). Distances are computed in each site's UTM zone (43N, 44N or 45N). A tenth candidate, Pirana (Ahmedabad), was left out because a persistent industrial heat source on the site dominates its detections from 2023.</p>
        <div className="ledger-wrap"><table className="ledger"><thead><tr><th>Site</th><th>City</th><th className="r">Area (ha)</th><th>Boundary</th></tr></thead>
          <tbody>{d.sites.map((s) => <tr key={s.site_id}><td>{s.name}</td><td>{s.city_name}</td><td className="num r">{s.area_ha}</td><td className="mono tiny method-wrap">{s.boundary_source} · {s.osm_id}</td></tr>)}</tbody></table></div>
      </Sec>

      <Sec id="detections" n={3} title="Detections">
        <p>NASA FIRMS VIIRS 375 m active-fire detections from Suomi NPP and NOAA-20: standard-processing (SP) archive from {String(f.start_date)} to the latest SP date, then near-real-time (NRT) to today. One bounding box per city; 5-day windows; raw CSV cached so nothing is fetched twice. Duplicates removed on (lat, lon to 4 dp, date, time, satellite), preferring SP over NRT. NOAA-21 (NRT only, from 2024) is used for live alerts but not for the counted history, so years stay comparable.</p>
        <p>A VIIRS pixel is about 375 m across at nadir and grows toward the edge of the swath; FIRMS gives its size as <code>scan × track</code> km. Each satellite passes over about twice a day (around 01:30 and 13:30 local time).</p>
      </Sec>

      <Sec id="attribution" n={4} title="Attribution: Tier A, B, C">
        <pre className="formula">{`footprint = rectangle scan × track km centred on the pixel centre
            (fallback ${a.fallback_scan_km} × ${a.fallback_track_km} km, flagged)
Tier A  pixel centre inside the site polygon
Tier B  footprint intersects the polygon, centre outside
Tier C  within ${a.tier_c_radius_m} m of the polygon, no intersection   → shown, never counted
counted = Tier A or B, confidence nominal/high${a.count_low_confidence ? ' or low' : ' (low kept separately)'}
fire day = IST date with ≥ 1 counted detection
episode  = run of fire days with gaps ≤ ${a.gap_days} day`}</pre>
        <p>Each detection is assigned to at most one site: best tier, then nearest. Example of why Tier C matters: about 300 night-time detections 1 km south of Bhalswa sit inside the Rajasthani Udyog Nagar industrial area (OSM). They are Tier C and never counted.</p>
      </Sec>

      <Sec id="smoke-days" n={5} title="Smoke Days (downwind rule)">
        <pre className="formula">{`for target point P and site S, on each fire day of S:
  d  = distance(S polygon edge, P)          skip if d > R = ${w.radius_km} km
  b  = bearing(S centroid → P)               geodesic, WGS84
  hours h = the ${w.window_hours} hourly samples from the IST hour of the first counted detection
  wd_to(h) = (wd_from(h) + 180) mod 360
  downwind(h) = ws(h) ≥ ${w.ws_min_ms} m/s  and  |b − wd_to(h)| ≤ ${w.half_width_deg}°
  calm(h)     = ws(h) < ${w.ws_min_ms} m/s           (counted separately)
Smoke Day for P = a fire day of any site within R with ≥ ${w.min_hours} downwind hour(s)`}</pre>
        <p>Wind: Open-Meteo historical API, hourly 10 m wind, ECMWF IFS 9 km where available, filled from ERA5-Land (0.1°) then ERA5 (0.25°); the model is recorded for every hour. Recent days not yet in the archive use the forecast API. A 9 km wind cannot resolve street-level flow, buildings or the plume's real path. Smoke Days is a <TierChip tier="MODELLED" /> count of days the wind pointed at a place, not a measure of smoke or exposure.</p>
        <p>The same rule applied to each OSM school within 3 km of a site gives “schools downwind on a fire day”.</p>
      </Sec>

      <Sec id="context" n={6} title="Neighbourhood context">
        <p>Buildings (<code>building=*</code>), schools (<code>amenity=school|college|kindergarten</code>) and hospitals (<code>amenity=hospital|clinic</code>) mapped in OpenStreetMap inside the site polygon buffered by 1 km and 3 km <TierChip tier="COUNTED" />. Population: WorldPop 2020 unconstrained 100 m grid summed over the same rings <TierChip tier="ESTIMATED" />, shown rounded to the nearest thousand.</p>
        <p>Ranking: <code>score = fire_days_last_365 × log10(1 + people_1km_est)</code>; sites with no counted detection in the last 365 days are listed as “no detections”.</p>
      </Sec>

      <Sec id="burn-scan" n={7} title="Burn Scan">
        <pre className="formula">{`scenes: Sentinel-2 L2A (Earth Search STAC, AWS Open Data), 10 days before to 10 days after an episode,
        cloud < 30 % and SCL clear over the polygon
NBR  = (B8A − B12) / (B8A + B12)        20 m grid
dNBR = NBR_pre − NBR_post;  burn mask where dNBR > threshold, inside the polygon
hot surface (heuristic): B12 above threshold and B12 > B11 > B8A
area = pixels × 0.04 ha;  range = area ± 0.5 × boundary pixels × 0.04 ha`}</pre>
        <p>Many episodes have no clear scene (clouds, smoke, 5-day revisit). Then we say so. Crops use a linear 2–98 % stretch; no AI upscaling or sharpening.</p>
      </Sec>

      <Sec id="validation" n={8} title="Validation against news">
        <p>Hit: a counted detection within ±{v.slack_days} day of a news-reported fire (night overpasses after midnight IST fall on the next date). {v.hits} of {v.total} linked reports have a hit.</p>
        <div className="ledger-wrap">
          <table className="ledger"><thead><tr><th>Site</th><th>Reported</th><th>Source</th><th>Hit</th><th className="r">Detections</th><th className="r">Max FRP</th></tr></thead>
            <tbody>{v.events.map((e) => <tr key={e.url}><td>{d.siteById[e.site_id]?.name ?? e.site_id}</td><td className="num">{dateLabel(e.date_start)}{e.date_end !== e.date_start ? ` – ${dateLabel(e.date_end)}` : ''}</td><td><a href={e.url} target="_blank" rel="noreferrer">{e.outlet}</a></td><td>{e.hit ? 'hit' : 'miss'}</td><td className="num r">{e.detections}</td><td className="num r">{e.max_frp_mw ?? '—'}</td></tr>)}</tbody></table>
        </div>
        <p className="small">{v.fire_days_without_news} detected fire days have no report in our list. {v.note}</p>
      </Sec>

      <Sec id="briefs" n={9} title="Briefs">
        <p>A short text per site. The model receives only a strict JSON of the record's numbers. Every number in the output must appear in that JSON, or the text is regenerated (at most twice) and then replaced by a fixed template. Banned words (blame, health and “saved/prevented” language) are linted. Hindi is a draft translation marked for human review.</p>
      </Sec>

      <Sec id="alerts" n={10} title="Alerts">
        <p>Every 30 minutes, EventBridge Scheduler starts the Watch state machine: fetch FIRMS NRT (SNPP, NOAA-20, NOAA-21) for each city, attribute, de-duplicate; for each new counted detection, fetch the next 12 h of forecast wind and run the downwind rule for each subscriber. If downwind for at least one hour, Amazon SNS sends an email with the detection, the window and a link to the official air-quality index. Time to alert = alert sent − first seen by our system; FIRMS publishes NRT data roughly 1–3 hours after the overpass, which is reported separately. Replays of past detections are labelled REPLAY.</p>
      </Sec>

      <Sec id="sources" n={11} title="Sources and licences">
        <ul className="sources">{d.sources.map((s) => <li key={s.id}><a href={s.url} target="_blank" rel="noreferrer">{s.name}</a> · {s.licence}. <span className="muted small">{s.attribution} Used for: {s.used_for}.</span></li>)}</ul>
      </Sec>

      <Sec id="prior-work" n={12} title="Prior work">
        <p>Satellite and sensor surveillance of waste fires is not new. Smoulder is not a new detection method; it is a public, per-site, per-address record with alerts. Related work we read:</p>
        <ul>
          <li>“Waste fire surveillance: a case study using remote sensing data and IoT ground sensing”, <i>Waste Management</i> (2026).</li>
          <li>Air-quality impacts of the 2023 Brahmapuram fire, <i>Science of the Total Environment</i> (2024).</li>
          <li>NASA FIRMS documentation and VIIRS 375 m active fire product (Schroeder et al., 2014).</li>
        </ul>
        <p className="small muted">We did not find a public, per-site, per-address record with alerts for Indian landfills; we may have missed one.</p>
      </Sec>

      <Sec id="limits" n={13} title="Limits"><Limits /></Sec>

      <Sec id="reproduce" n={14} title="How to reproduce a number">
        <pre className="formula">{`git clone … && make setup            # Python venv + web deps
echo FIRMS_MAP_KEY=… > .env
make backfill-local                    # FIRMS → cache/raw, attribution → cache/derived
make gate                              # validation table → docs/GATE.md
python -m pipeline.publish.snapshot    # wind, context, Smoke Days → web/public/data/snapshot.json
# e.g. Bhalswa fire days in 2022:
jq '[.fire_days[] | select(.site_id=="bhalswa" and (.date_ist|startswith("2022")))] | length' web/public/data/snapshot.json`}</pre>
      </Sec>
    </main>
  );
}

function Sec({ id, n, title, children }: { id: string; n: number; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="sec method-sec">
      <div className="sec-head"><span className="sec-no">{String(n).padStart(2, '0')}</span><h2>{title}</h2></div>
      {children}
    </section>
  );
}
