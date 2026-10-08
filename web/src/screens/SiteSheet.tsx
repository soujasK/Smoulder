import { useEffect, useMemo, useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useT } from '../i18n';
import { useSnapshot, type Indexed } from '../data/snapshot';
import type { Detection, Site } from '../types/contract';
import { Scene3D, type View } from '../three/Scene3D';
import { Columns, Footprint, Outline, SectorOutline } from '../three/Overlays';
import { StillView } from '../three/StillView';
import { Frame, useTerrainData } from '../three/terrainData';
import { Calendar, type CellKind } from '../components/Calendar';
import { Metric, TierChip } from '../components/Tier';
import { Subscribe } from '../components/Subscribe';
import { Limits } from '../components/Limits';
import { BurnScan } from '../components/BurnScan';
import { CONF, dateLabel, fixed, int, km, SAT, toIST } from '../lib/format';
import './site.css';

export function pickExamples(dets: Detection[]): Record<'A' | 'B' | 'C', Detection | undefined> {
  const by = (tier: string) => dets.filter((d) => d.tier === tier).sort((a, b) => (b.frp_mw ?? 0) - (a.frp_mw ?? 0) || b.ts_utc.localeCompare(a.ts_utc))[0];
  return { A: by('A'), B: by('B'), C: dets.filter((d) => d.tier === 'C').sort((a, b) => a.dist_m - b.dist_m)[0] };
}

export function SiteSheet() {
  const { id = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const { t, lang } = useT();
  const snap = useSnapshot();
  const d = snap.data;
  const site = d?.siteById[id];
  const dets = useMemo(() => (d ? d.detBySite[id] ?? [] : []), [d, id]);
  const fds = useMemo(() => (d ? d.fdBySite[id] ?? [] : []), [d, id]);
  const eps = useMemo(() => (d ? d.epBySite[id] ?? [] : []), [d, id]);
  const lastYear = d ? String(Number(d.data_through.slice(0, 4)) - 1) : '2025';
  const [year, setYear] = useState<string>(params.get('year') ?? '');
  useEffect(() => {
    if (!year && site) {
      // default: most recent year with fire days, else last full year
      const ys = Object.entries(site.stats.fire_days_by_year).filter(([, n]) => n > 0).map(([y]) => y).sort();
      setYear(ys.length ? ys[ys.length - 1] : lastYear);
    }
  }, [site, year, lastYear]);
  const [pixTier, setPixTier] = useState<'A' | 'B' | 'C'>((params.get('pixel') as 'A' | 'B' | 'C') || 'A');
  const examples = useMemo(() => pickExamples(dets), [dets]);
  const [scrub, setScrub] = useState(1);

  if (!d) return null;
  if (!site) return <main id="main" className="page"><p>Unknown site.</p></main>;

  const idx = d.sites.findIndex((s) => s.site_id === id) + 1;
  const yearDets = dets.filter((x) => x.date_ist.startsWith(year));
  const yearFds = fds.filter((f) => f.date_ist.startsWith(year));
  const news = d.validation.events.filter((e) => e.site_id === id);
  const ticks = new Set<string>();
  for (const e of news) {
    let cur = e.date_start;
    while (cur <= e.date_end) { ticks.add(cur); cur = new Date(Date.parse(cur) + 86400000).toISOString().slice(0, 10); }
  }
  const cells: Record<string, CellKind> = {};
  for (const x of yearDets) if (x.low_conf_ab && !cells[x.date_ist]) cells[x.date_ist] = 'low';
  for (const f of yearFds) cells[f.date_ist] = 'fill';
  const ctx = site.context;
  const years = Object.keys(site.stats.fire_days_by_year).sort().reverse();
  const sectors = d.sectors.filter((s) => s.site_id === id && s.date_ist.startsWith(year));
  const ex = examples[pixTier];
  const counted = dets.filter((x) => x.counted).sort((a, b) => a.ts_utc.localeCompare(b.ts_utc));
  const scrubIdx = Math.round(scrub * Math.max(0, counted.length - 1));
  const scrubTs = counted[scrubIdx]?.ts_utc ?? null;
  const brief = d.briefs.find((b) => b.site_id === id && b.lang === lang) ?? d.briefs.find((b) => b.site_id === id && b.lang === 'en');
  const view: View = { lon: site.centroid[0], lat: site.centroid[1], distance: params.get('pixel') ? 2600 : 3600, azimuth: 20, elevation: 42 };
  const summary = `3D view of ${site.name} landfill on Copernicus DEM terrain with a Sentinel-2 drape; ${counted.length} counted detections as ember columns; the ${pixTier === 'A' ? 'Tier A' : pixTier === 'B' ? 'Tier B' : 'Tier C'} example pixel footprint is outlined.`;
  const firmsReceipt = { source: 'NASA FIRMS VIIRS 375 m (SNPP, NOAA-20)', method: 'Tier A/B detections, nominal or high confidence, IST dates', date: `${site.stats.first_data_date} to ${site.stats.data_through}`, href: '/method#attribution' };
  const osmReceipt = { source: '© OpenStreetMap contributors (ODbL), via Overpass', method: 'Mapped features inside the site polygon buffered by 1 km / 3 km', date: ctx?.retrieved_on ?? '—', href: '/method#context' };
  const popReceipt = { source: 'WorldPop 2020, 100 m (CC BY 4.0)', method: 'Sum of gridded population inside the buffered polygon', date: '2020 estimate', href: '/method#context' };

  return (
    <main id="main" className="site page">
      <header className="site-head">
        <div className="site-runhead mono tiny">
          <span>{t('site.record')}</span><span>Record {String(idx).padStart(2, '0')} / {String(d.sites.length).padStart(2, '0')}</span>
          <span>{site.centroid[1].toFixed(4)}°N {site.centroid[0].toFixed(4)}°E</span><span>{site.area_ha} ha · boundary: {site.boundary_source} {site.osm_id}</span>
        </div>
        <h1 className="serif site-title">{site.name}<span className="site-city">{site.city_name}</span></h1>
        <div className="site-actions">
          <Link className="btn btn-ghost" to={`/print/site/${id}`}>{t('site.print')}</Link>
        </div>
      </header>

      <section className="site-3d">
        <div className="site-3d-main">
          <Scene3D terrainId={id} view={view} summary={summary} drapeOpacity={0.62} height="min(64vh, 620px)">
            {(frame) => (
              <>
                <Outline frame={frame} geom={site.polygon} width={1.8} step={10} lift={2} />
                {d.sites.filter((s) => s.site_id !== id).map((s) => <Outline key={s.site_id} frame={frame} geom={s.polygon} width={1} step={20} opacity={0.5} />)}
                <Columns frame={frame} dets={dets} maxHeight={260} dayOf={colIndex} now={scrubTs ? tsIndex(scrubTs) + 7 : -1} />
                {ex && <Footprint frame={frame} det={ex} label={`Tier ${ex.tier} · ${dateLabel(ex.date_ist)}`} color={pixTier === 'C' ? '#8C8F8A' : '#F4C77A'} />}
                {sectors.map((s) => <SectorOutline key={s.date_ist} frame={frame} sector={s} opacity={0.6} />)}
              </>
            )}
          </Scene3D>
          <div className="scrubber">
            <label className="label" htmlFor="scrub">{t('site.scrub')}</label>
            <input id="scrub" type="range" min={0} max={1} step={0.001} value={scrub} onChange={(e) => setScrub(Number(e.target.value))} aria-valuetext={scrubTs ? dateLabel(toIST(scrubTs).date) : 'none'} />
            <span className="mono tiny">{scrubTs ? `${dateLabel(toIST(scrubTs).date, lang)} · ${scrubIdx + 1}/${counted.length}` : 'no counted detections'}</span>
          </div>
          <p className="fig-cap"><span className="fig-no">Fig. 1.</span>{site.name}, 4 × 4 km. Copernicus DEM GLO-30 (2011–2015) contours every 2 m; Sentinel-2 L2A drape; columns are VIIRS detections (height and colour by FRP, log scale; grey = not counted). Wind sectors for {year} fire days.</p>
        </div>
        <aside className="site-pixel" aria-labelledby="pix-h">
          <h2 id="pix-h" className="label">{t('site.pixel')}</h2>
          <div className="pix-tabs" role="tablist">
            {(['A', 'B', 'C'] as const).map((k) => (
              <button key={k} role="tab" aria-selected={pixTier === k} className={pixTier === k ? 'on' : ''} disabled={!examples[k]} onClick={() => { setPixTier(k); setParams((p) => { p.set('pixel', k); return p; }, { replace: true }); }}>Tier {k}</button>
            ))}
          </div>
          {ex ? <PixelTruth site={site} det={ex} /> : <p className="small muted">No Tier {pixTier} detection at this site.</p>}
        </aside>
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">01</span><h2>{t('site.firedays')}</h2></div>
        <div className="metrics">
          <Metric label={`Fire days, ${year}`} value={yearFds.length || (yearFds.length === 0 ? '0' : '')} unit="days" tier="MEASURED" receipt={firmsReceipt} />
          <Metric label="Fire days, last 365 d" value={site.stats.fire_days_365} unit="days" tier="MEASURED" receipt={firmsReceipt} />
          <Metric label="Counted detections, all years" value={int(site.stats.detections_counted)} tier="MEASURED" receipt={firmsReceipt} />
          <Metric label="Max FRP" value={fixed(site.stats.max_frp_mw, 1)} unit="MW" tier="MEASURED" receipt={{ ...firmsReceipt, method: 'Largest fire radiative power of a counted detection' }} />
          <Metric label="Last counted detection" value={site.stats.last_detection_utc ? dateLabel(toIST(site.stats.last_detection_utc).date, lang) : '—'} tier="MEASURED" receipt={firmsReceipt} />
        </div>
        <table className="ledger years">
          <thead><tr><th>Year</th><th className="r">Fire days</th><th></th></tr></thead>
          <tbody>
            {years.map((y) => {
              const n = site.stats.fire_days_by_year[y];
              return (
                <tr key={y} className={y === year ? 'is-on' : ''}>
                  <td><button className="linkish mono" onClick={() => setYear(y)}>{y}</button>{y === d.data_through.slice(0, 4) && <span className="tiny muted"> to {dateLabel(d.data_through, lang)}</span>}</td>
                  <td className="num r">{n > 0 ? n : ''}</td>
                  <td>{n > 0 ? <span className="bar" style={{ width: `${Math.min(100, n * 6)}%` }} /> : <span className="tiny muted">no detections</span>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">02</span><h2>{t('site.calendar')}, {year}</h2></div>
        <Calendar year={Number(year)} cells={cells} ticks={ticks} caption={`${site.name} detection calendar ${year}`} legend={{ fill: 'fire day (Tier A/B)', low: 'low-confidence only, not counted', tick: 'news-reported' }} through={d.data_through} start={site.stats.first_data_date} />
        {yearFds.length === 0 && <p className="small muted">No counted detections at {site.name} in {year}.</p>}
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">03</span><h2>{t('site.episodes')}</h2></div>
        {eps.length === 0 ? <p className="small muted">No episodes: no counted detections.</p> : (
          <div className="ledger-wrap">
            <table className="ledger">
              <thead><tr><th>Start</th><th>End</th><th className="r">Fire days</th><th className="r">Span</th><th className="r">Detections</th><th className="r">Max FRP (MW)</th></tr></thead>
              <tbody>{[...eps].reverse().map((e) => (
                <tr key={e.start_date}><td className="num">{dateLabel(e.start_date, lang)}</td><td className="num">{dateLabel(e.end_date, lang)}</td><td className="num r">{e.fire_days}</td><td className="num r">{e.span_days} d</td><td className="num r">{e.detections}</td><td className="num r">{fixed(e.max_frp_mw)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <p className="tiny muted">Episode: consecutive fire days with gaps of at most {String((d.parameters.attribution as Record<string, number>).gap_days)} day. All values MEASURED (satellite).</p>
      </section>

      <BurnScan site={site} obs={d.burn_obs.filter((b) => b.site_id === id)} />

      <section className="sec">
        <div className="sec-head"><span className="sec-no">05</span><h2>{t('site.neighbours')}</h2></div>
        {ctx ? (
          <div className="metrics">
            <Metric label="Buildings within 1 km" value={int(ctx.buildings_1km)} tier="COUNTED" receipt={osmReceipt} />
            <Metric label="Buildings within 3 km" value={int(ctx.buildings_3km)} tier="COUNTED" receipt={osmReceipt} />
            <Metric label="Schools/colleges 1 km · 3 km" value={`${ctx.schools_1km} · ${ctx.schools_3km}`} tier="COUNTED" receipt={osmReceipt} />
            <Metric label="Hospitals/clinics 1 km · 3 km" value={`${ctx.hospitals_1km} · ${ctx.hospitals_3km}`} tier="COUNTED" receipt={osmReceipt} />
            <Metric label="Nearest school" value={ctx.nearest_school_m !== null ? km(ctx.nearest_school_m) : '—'} tier="COUNTED" receipt={osmReceipt} />
            <Metric label="People within 1 km" value={`~${int(Math.round(ctx.people_1km_est / 1000) * 1000)}`} tier="ESTIMATED" receipt={popReceipt} />
            <Metric label="People within 3 km" value={`~${int(Math.round(ctx.people_3km_est / 1000) * 1000)}`} tier="ESTIMATED" receipt={popReceipt} />
            {site.schools_downwind && (
              <Metric label={`Schools downwind on a fire day, ${site.schools_downwind.year}`} value={`${site.schools_downwind.schools_downwind_any_day} of ${site.schools_downwind.schools_considered}`} tier="MODELLED"
                receipt={{ source: 'OSM schools within 3 km; NASA FIRMS; Open-Meteo wind', method: 'Smoke Days rule applied to each school', date: String(site.schools_downwind.year), href: '/method#smoke-days' }} />
            )}
          </div>
        ) : <p className="small muted">Neighbourhood counts not available for this site yet.</p>}
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">06</span><h2>{t('site.sectors')}, {year}</h2></div>
        <SectorsPlan site={site} d={d} year={year} />
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">07</span><h2>{t('site.validation')}</h2></div>
        {news.length === 0 ? <p className="small muted">No linked news reports for this site in our compiled list.</p> : (
          <div className="ledger-wrap">
            <table className="ledger">
              <thead><tr><th>Reported</th><th>Outlet</th><th>Detected (±{d.validation.slack_days} d)</th><th className="r">Detections</th><th>Tier</th></tr></thead>
              <tbody>{news.map((e) => (
                <tr key={e.url}><td className="num">{dateLabel(e.date_start, lang)}{e.date_end !== e.date_start ? ` – ${dateLabel(e.date_end, lang)}` : ''}</td><td><a href={e.url} target="_blank" rel="noreferrer">{e.outlet}</a></td><td>{e.hit ? `yes, ${e.detection_dates.map((x) => dateLabel(x, lang)).join(', ')}` : 'no counted detection'}</td><td className="num r">{e.detections}</td><td><TierChip tier="COMPILED" /></td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <p className="small" data-metric>
          <span className="num">{d.validation.by_site[id]?.unreported ?? 0}</span> of <span className="num">{d.validation.by_site[id]?.fire_days ?? 0}</span> detected fire days had no news report we could find. <TierChip tier="COMPILED" />
          <span className="tiny muted" data-receipt> Compared with data/news_fires.csv ({d.validation.total} linked reports). Our list is short; absence of a report in it does not mean no one reported the fire.</span>
        </p>
      </section>

      {brief && (
        <section className="sec">
          <div className="sec-head"><span className="sec-no">08</span><h2>{t('site.brief')}</h2><span className="tag">{brief.label}</span></div>
          <p className={`brief ${brief.lang === 'hi' ? 'serif' : 'serif'}`} lang={brief.lang}>{brief.text}</p>
          <p className="tiny muted">{brief.generator === 'bedrock' ? `Amazon Bedrock (${brief.model_id}); every number checked against the record` : 'Template text; every number comes from the record'} · run {brief.run_id}</p>
        </section>
      )}

      <section className="sec site-limits"><Limits /></section>

      <section className="sec">
        <Subscribe lon={site.centroid[0]} lat={site.centroid[1]} />
      </section>
    </main>
  );
}

// day index for the time scrubber (days since 2019-01-01, from the UTC timestamp)
const tsIndex = (ts: string) => Math.floor(Date.parse(ts.replace('Z', ':00Z')) / 86400000) - 17897;
const colIndex = (d: Detection) => tsIndex(d.ts_utc);

function PixelTruth({ site, det }: { site: Site; det: Detection }) {
  const scan = det.scan_km ?? 0.375, track = det.track_km ?? 0.375;
  const px = scan * track * 100;
  const ist = toIST(det.ts_utc);
  const why = det.tier === 'A' ? 'The pixel centre is inside the site boundary: Tier A.'
    : det.tier === 'B' ? `The pixel centre is ${km(det.dist_m)} outside the boundary, but its footprint overlaps the site: Tier B.`
      : `The pixel centre is ${km(det.dist_m)} from the boundary and its footprint does not overlap the site: Tier C. Shown, never counted.`;
  return (
    <div className="pix" data-metric>
      <p className="serif pix-s">One satellite pixel here is about <span className="num">{px.toFixed(0)}</span> ha. This site is about <span className="num">{site.area_ha.toFixed(0)}</span> ha.</p>
      <p className="small">{why}</p>
      <TierChip tier="MEASURED" />
      <dl className="kv" data-receipt>
        <dt>When</dt><dd className="mono">{dateLabel(ist.date)} {ist.time} IST</dd>
        <dt>Satellite</dt><dd>VIIRS {SAT[det.satellite] ?? det.satellite} ({det.source.endsWith('_SP') ? 'standard' : 'near real-time'})</dd>
        <dt>Footprint</dt><dd className="mono">{scan.toFixed(2)} × {track.toFixed(2)} km{det.fallback_footprint ? ' (assumed)' : ''}</dd>
        <dt>FRP</dt><dd className="mono">{fixed(det.frp_mw, 2)} MW</dd>
        <dt>Confidence</dt><dd>{CONF[det.confidence] ?? det.confidence}</dd>
        <dt>Position</dt><dd className="mono">{det.lat.toFixed(4)}, {det.lon.toFixed(4)}</dd>
      </dl>
      <p className="tiny muted">Pixel size grows away from the satellite's ground track (scan × track from FIRMS). A detection says a pixel was hot at overpass time; it does not say how much burned.</p>
    </div>
  );
}

function SectorsPlan({ site, d, year }: { site: Site; d: Indexed; year: string }) {
  const terr = useTerrainData(`${site.city}-city`);
  const frame = useMemo(() => (terr ? new Frame(terr) : null), [terr]);
  if (!frame) return <div className="skeleton" />;
  const sectors = d.sectors.filter((s) => s.site_id === site.site_id && s.date_ist.startsWith(year));
  return (
    <div className="sectors-plan">
      <StillView frame={frame} drape={false} layers={{ polygons: d.sites.filter((s) => s.city === site.city).map((s) => ({ geom: s.polygon, kind: 'site' as const })), sectors, labels: d.sites.filter((s) => s.city === site.city).map((s) => ({ lon: s.centroid[0], lat: s.centroid[1], text: s.name })) }}
        caption={`Fig. 2. Downwind sectors (thin lines, radius ${(d.parameters.downwind as Record<string, number>).radius_km} km) for ${sectors.length} fire day${sectors.length === 1 ? '' : 's'} at ${site.name} in ${year}, from hourly Open-Meteo wind in the ${(d.parameters.downwind as Record<string, number>).window_hours} h after the first detection. MODELLED.`} />
      {sectors.length === 0 && <p className="small muted">No fire days at {site.name} in {year}, so no sectors.</p>}
    </div>
  );
}
