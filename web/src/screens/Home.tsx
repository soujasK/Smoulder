import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useT } from '../i18n';
import { fetchSmokeDays, liveEnabled, useSnapshot, type Indexed } from '../data/snapshot';
import type { DownwindResult, Landmark, SmokeDaysResponse } from '../types/contract';
import { Scene3D, useReducedMotion, type View } from '../three/Scene3D';
import { Columns, Outline, Pin, SectorOutline, SiteLabel } from '../three/Overlays';
import { Calendar, type CellKind } from '../components/Calendar';
import { TierChip } from '../components/Tier';
import { Subscribe } from '../components/Subscribe';
import { EmberLedger } from '../components/EmberLedger';
import { dateLabel, hourIST, km } from '../lib/format';
import { dayOfYear, daysInYear, isoFromDay, usePlayer } from '../lib/usePlayer';
import { useDemo } from '../demo/useDemo';
import './home.css';

type Answer = { label: string; result: DownwindResult; city: string; lon: number; lat: number; sample: boolean };

function findLandmarks(d: Indexed, q: string): Landmark[] {
  const s = q.trim().toLowerCase();
  if (!s) return [];
  return d.landmarks.filter((l) => l.name.toLowerCase().includes(s));
}

export function Home() {
  const { t, lang } = useT();
  const snap = useSnapshot();
  const [params] = useSearchParams();
  const demo = useDemo(params.get('demo') === '1');
  const d = snap.data;
  const [q, setQ] = useState('');
  const [year, setYear] = useState<string>('');
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [status, setStatus] = useState<SmokeDaysResponse['status'] | 'idle' | 'loading' | 'error'>('idle');
  const [candidates, setCandidates] = useState<{ label: string; lon: number; lat: number }[]>([]);
  const [outside, setOutside] = useState<{ label: string; siteId: string; site: string; km: number; dir: string } | null>(null);
  const [pickDay, setPickDay] = useState<string | null>(null);
  const reduced = useReducedMotion();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (d && !year) setYear(params.get('year') ?? 'all'); }, [d, year, params]);
  // shareable answers: /?q=<place>&year=<yyyy|all>
  const autoRan = useRef(false);
  useEffect(() => {
    const q0 = params.get('q');
    if (!d || !year || !q0 || autoRan.current || params.get('demo') === '1') return;
    autoRan.current = true;
    setQ(q0);
    void run(q0, year);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, year]);

  const years = useMemo(() => {
    if (!d) return [];
    const ys: string[] = [];
    for (let y = Number(d.data_through.slice(0, 4)); y >= Number(d.sites[0]?.stats.first_data_date.slice(0, 4) ?? 2019); y--) ys.push(String(y));
    return ['all', ...ys];
  }, [d]);

  async function run(text: string, y: string) {
    if (!d || !text.trim()) return;
    setPickDay(null);
    setCandidates([]);
    setOutside(null);
    // A curated public station (Demo Mode, sample links) always resolves to its own point, never a geocoder's guess.
    const exact = d.landmarks.find((l) => l.name.toLowerCase() === text.trim().toLowerCase());
    if (liveEnabled && !exact) {
      setStatus('loading');
      try {
        const r = await fetchSmokeDays(text, y);
        setStatus(r.status);
        if (r.status === 'ambiguous') setCandidates(r.candidates);
        if (r.status === 'outside_coverage' && r.candidates?.length) setOutside(nearestSite(d, r.candidates[0]));
        if (r.status === 'ok' && r.result) {
          const near = r.result.nearest_sites[0];
          setAnswer({ label: r.label, result: r.result, city: near ? d.siteById[near.site_id].city : 'delhi', lon: r.result.point[0], lat: r.result.point[1], sample: r.sample });
        }
        return;
      } catch {
        setStatus('error');
      }
    }
    // offline: landmarks in the snapshot
    const m = findLandmarks(d, text);
    if (m.length === 0) { setStatus('not_found'); setAnswer(null); return; }
    if (m.length > 1 && !m.some((l) => l.name.toLowerCase() === text.trim().toLowerCase())) {
      setStatus('ambiguous');
      setCandidates(m.slice(0, 6).map((l) => ({ label: l.name, lon: l.lon, lat: l.lat })));
      return;
    }
    const l = m.find((x) => x.name.toLowerCase() === text.trim().toLowerCase()) ?? m[0];
    const res = l.results[y];
    if (!res) { setStatus('not_found'); return; }
    setStatus('ok');
    setAnswer({ label: l.name, result: res, city: l.city, lon: l.lon, lat: l.lat, sample: true });
  }

  // Demo Mode drives the form
  useEffect(() => {
    if (!demo.active || !d) return;
    if (demo.year && demo.year !== year) setYear(demo.year);
    if (demo.typed !== undefined) setQ(demo.typed);
    if (demo.submit) void run(demo.submit, demo.year ?? year);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demo.step]);

  function onSubmit(e: FormEvent) { e.preventDefault(); void run(q, year); }

  const res = answer?.result ?? null;
  const all = year === 'all';
  const firstYear = d ? Number(d.sites[0]?.stats.first_data_date.slice(0, 4) ?? 2019) : 2019;
  const yr = all ? firstYear : Number(year || 0);
  const spanStart = `${yr || 2024}-01-01`;
  const nDays = all && d ? spanDays(spanStart, d.data_through) : daysInYear(yr || 2024);
  const playKey = res ? `${answer?.label}:${year}` : null;
  const player = usePlayer(playKey, (demo.active ? demo.yearMs : 9000) * (all ? 1.6 : 1), !reduced, demo.active ? 600 : 300);
  const nowDay = player.p * nDays;
  const nowIso = isoFromDay(yr || 2024, Math.min(nDays - 1, nowDay));
  const dayIdx = (iso: string) => (all ? spanDays(spanStart, iso) - 1 : dayOfYear(iso));
  const smokeSet = useMemo(() => new Set(res?.days.map((x) => x.date_ist) ?? []), [res]);
  const colDay = useMemo(() => (x: { date_ist: string }) => (all ? spanDays(spanStart, x.date_ist) - 1 : dayOfYear(x.date_ist)), [all, spanStart]);
  const shownCount = res ? res.days.filter((x) => dayIdx(x.date_ist) <= nowDay).length : 0;

  const city = answer?.city ?? demo.city ?? 'delhi';
  const citySites = useMemo(() => d?.sites.filter((s) => s.city === city) ?? [], [d, city]);
  const cityDets = useMemo(() => (d ? d.detections.filter((x) => citySites.some((s) => s.site_id === x.site_id) && (year === 'all' || x.date_ist.startsWith(year))) : []), [d, citySites, year]);
  const smokeSectors = useMemo(() => {
    if (!d || !res) return [];
    const ids = new Set(res.nearest_sites.map((n) => n.site_id));
    return d.sectors.filter((s) => ids.has(s.site_id) && smokeSet.has(s.date_ist));
  }, [d, res, smokeSet]);

  const view: View | null = useMemo(() => {
    if (demo.active && demo.view) return demo.view;
    if (!d) return null;
    if (answer) {
      const near = answer.result.nearest_sites[0];
      const s = near ? d.siteById[near.site_id] : null;
      const lon = s ? (answer.lon + s.centroid[0]) / 2 : answer.lon;
      const lat = s ? (answer.lat + s.centroid[1]) / 2 : answer.lat;
      const dist = near ? Math.max(9000, near.distance_m * 4) : 9000;
      return { lon, lat, distance: dist, azimuth: near ? near.bearing_deg + 180 : 20, elevation: 34 };
    }
    const cs = d.sites.filter((s) => s.city === city);
    const lons = cs.map((s) => s.centroid[0]), lats = cs.map((s) => s.centroid[1]);
    const lon = (Math.min(...lons) + Math.max(...lons)) / 2, lat = (Math.min(...lats) + Math.max(...lats)) / 2;
    const spanM = Math.max((Math.max(...lons) - Math.min(...lons)) * 98000, (Math.max(...lats) - Math.min(...lats)) * 111000);
    return { lon, lat: lat - spanM / 111000 * 0.08, distance: Math.max(16000, spanM * 1.7 + 8000), azimuth: 6, elevation: 56 };
  }, [d, answer, city, demo.active, demo.view]);

  if (!d) return null;

  const r = d.parameters.downwind as Record<string, number>;
  const summary = answer
    ? `3D terrain of ${citySites.map((s) => s.name).join(', ')} with detections for ${year}, wind sectors for each smoke day and a pin at ${answer.label}.`
    : `3D contour terrain of ${city}, showing landfill sites ${citySites.map((s) => s.name).join(', ')}.`;

  const cells: Record<string, CellKind> = {};
  if (res) {
    for (const dd of res.calm) cells[dd.date_ist] = 'low';
    for (const dd of res.days) cells[dd.date_ist] = 'fill';
  }
  const fireDaysNearbyOnly = res ? res.fire_days_nearby - res.smoke_days - res.calm_days : 0;
  const picked = pickDay ? res?.days.find((x) => x.date_ist === pickDay) ?? res?.calm.find((x) => x.date_ist === pickDay) : null;
  const sampleLm = [...d.landmarks].sort((x, y) => (y.results.all?.smoke_days ?? 0) - (x.results.all?.smoke_days ?? 0)).slice(0, 3);

  return (
    <main id="main" className="home">
      <div className="home-grid page">
        <section className="home-left" aria-labelledby="q">
          <p className="label home-kicker"><span className="ember-dot" aria-hidden />{t('home.kicker')}</p>
          <h1 id="q" className="serif home-q">
            {demo.active && demo.question !== undefined ? <span>{demo.question}<span className="caret" aria-hidden /></span> : t('home.question')}
          </h1>
          <p className="home-sub">{t('home.sub')}</p>
          <form className="home-form" onSubmit={onSubmit} role="search">
            <label className="field home-field">
              <span className="label">{t('home.input.label')}</span>
              <input ref={inputRef} className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={liveEnabled ? t('home.input.placeholder') : t('home.input.offline')} list={liveEnabled ? undefined : 'landmarks'} autoComplete="off" />
              {!liveEnabled && <datalist id="landmarks">{d.landmarks.map((l) => <option key={l.id} value={l.name} />)}</datalist>}
            </label>
            <label className="field home-year">
              <span className="label">{t('home.year')}</span>
              <select className="select mono" value={year} onChange={(e) => { setYear(e.target.value); if (answer) void run(answer.label, e.target.value); }}>
                {years.map((y) => <option key={y} value={y}>{y === 'all' ? `${firstYear}–${d.data_through.slice(0, 4)}` : y}{y === d.data_through.slice(0, 4) ? ' (to date)' : ''}</option>)}
              </select>
            </label>
            <button className="btn home-go" type="submit" disabled={status === 'loading'}>{t('home.submit')}</button>
          </form>
          {!liveEnabled && sampleLm.length > 0 && !answer && (
            <p className="tiny muted home-try">
              {t('home.sample')}: {sampleLm.map((l, i) => <span key={l.id}>{i > 0 && ' · '}<button className="linkish" onClick={() => { setQ(l.name); void run(l.name, year); }}>{l.name}</button></span>)}
            </p>
          )}

          {status === 'loading' && <div aria-busy className="skeleton" />}
          {status === 'not_found' && <p className="home-msg">{t('home.notfound')}</p>}
          {status === 'outside_coverage' && (outside ? (
            <div className="home-msg home-outside">
              <p>{t('home.outside.near', { place: outside.label, site: outside.site, km: outside.km, dir: outside.dir })}</p>
              <p className="small muted">{t('home.outside.why', { r: r.radius_km })} <Link to={`/site/${outside.siteId}`}>{t('home.outside.link', { site: outside.site })} →</Link></p>
            </div>
          ) : <p className="home-msg">{t('home.outside', { r: r.radius_km, sites: d.sites.map((s) => s.name).join(', ') })}</p>)}
          {status === 'error' && <p className="home-msg">{t('state.error', { date: dateLabel(d.data_through, lang) })}</p>}
          {status === 'ambiguous' && (
            <div className="home-msg">
              <p>{t('home.candidates')}</p>
              <ul className="cands">{candidates.map((c) => <li key={c.label}><button className="linkish" onClick={() => { setQ(c.label); void run(c.label, year); }}>{c.label}</button></li>)}</ul>
            </div>
          )}

          {answer && res && status === 'ok' && (
            <div className="answer" aria-live="polite">
              <div data-metric className="answer-block">
                {res.nearest_sites.length === 0 ? (
                  <p className="serif answer-s">{all ? t('home.answer.empty.all', { r: r.radius_km, from: firstYear, to: dateLabel(d.data_through, lang) }) : t('home.answer.empty', { r: r.radius_km, year })}</p>
                ) : (
                  <p className="serif answer-s">
                    {all ? t('home.answer.all', { from: firstYear, to: dateLabel(d.data_through, lang), area: answer.label }) : t('home.answer', { year, area: answer.label })}
                    <span className="answer-fig">
                      <span className="answer-n num" aria-label={`${res.smoke_days} ${t('home.answer.days')}`}>{player.playing ? shownCount : res.smoke_days}</span>
                      <span className="answer-u">{res.smoke_days === 1 ? t('home.answer.day') : t('home.answer.days')}</span>
                    </span>
                  </p>
                )}
                <div className="answer-meta">
                  <TierChip tier="MODELLED" />
                  <Link to="/method#smoke-days" className="small">{t('home.how')} →</Link>
                  {player.playing && <button className="linkish tiny" onClick={player.skip}>skip ▸</button>}
                  {answer.sample && !liveEnabled && <span className="tag">offline · precomputed</span>}
                </div>
                <p className="tiny muted" data-receipt>
                  {t('home.modelled.note')} Rule: downwind within ±{r.half_width_deg}° for ≥{r.min_hours} h in the {r.window_hours} h after the first counted detection, wind ≥{r.ws_min_ms} m/s, sites within {r.radius_km} km. Wind: Open-Meteo ({(res.days[0]?.sites[0]?.models ?? ['ecmwf_ifs']).join(', ')}). Detections: NASA FIRMS VIIRS. Data through {d.data_through}.
                </p>
                {res.nearest_sites.length > 0 && res.smoke_days === 0 && res.fire_days_nearby > 0 && (
                  <p className="small">{t('home.answer.nofire', { r: r.radius_km, n: res.fire_days_nearby, year })}</p>
                )}
              </div>

              <div className="ticker mono" aria-hidden>{player.playing ? dateLabel(nowIso, lang) : ''}</div>

              {res.nearest_sites.length > 0 && (
                <section className="answer-sec">
                  <h2 className="label">{t('home.nearest')}</h2>
                  <table className="ledger">
                    <tbody>
                      {res.nearest_sites.map((n) => (
                        <tr key={n.site_id}>
                          <td><Link to={`/site/${n.site_id}`}>{n.name}</Link></td>
                          <td className="num r">{km(n.distance_m)} {n.bearing_compass}</td>
                          <td className="num r">{n.fire_days} fire {n.fire_days === 1 ? 'day' : 'days'}{all ? '' : ` in ${year}`} <TierChip tier="MEASURED" /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="tiny muted">Distance from the site boundary; direction from the site to this place.</p>
                </section>
              )}

              {res.nearest_sites.length > 0 && (
                <section className="answer-sec">
                  {(all ? calYears(res) : [yr]).map((cy) => (
                    <div key={cy} className="cal-year">
                      <h2 className="label">{t('home.calendar', { year: cy })}</h2>
                      <Calendar
                        year={cy}
                        cells={cells}
                        highlight={pickDay}
                        onPick={setPickDay}
                        caption={`Calendar of smoke days at ${answer.label} in ${cy}`}
                        legend={{ fill: 'smoke day (modelled)', low: 'fire day, calm air' }}
                        through={d.data_through}
                        start={d.sites[0].stats.first_data_date}
                      />
                    </div>
                  ))}
                  {all && <p className="tiny muted">Years without a smoke day or calm fire day are not drawn.</p>}
                  {res.calm_days > 0 && <p className="tiny muted">{t('home.calm', { n: res.calm_days, ws: r.ws_min_ms })}</p>}
                  {fireDaysNearbyOnly > 0 && <p className="tiny muted">{fireDaysNearbyOnly} further fire day{fireDaysNearbyOnly === 1 ? '' : 's'} at nearby sites had wind blowing elsewhere.</p>}
                </section>
              )}

              {res.days.length > 0 && (
                <section className="answer-sec">
                  <h2 className="label">{t('home.receipts')}</h2>
                  <table className="ledger receipts">
                    <thead><tr><th>Date</th><th>Site</th><th className="r">Det.</th><th className="r">First seen</th><th className="r">Downwind</th><th>Wind</th></tr></thead>
                    <tbody>
                      {[...res.days, ...(picked && !smokeSet.has(picked.date_ist) ? [picked] : [])].map((dd) => dd.sites.map((s, i) => (
                        <tr key={dd.date_ist + s.site_id} className={pickDay === dd.date_ist ? 'is-picked' : ''}>
                          <td className="num" data-label="Date">{i === 0 ? dateLabel(dd.date_ist, lang) : ''}</td>
                          <td data-label="Site">{s.name}</td>
                          <td className="num r" data-label="Detections">{s.detections}</td>
                          <td className="num r" data-label="First seen (IST)">{hourIST(s.window_start_ist)}</td>
                          <td className="num r" data-label="Downwind">{s.downwind_hours}/{r.window_hours} h</td>
                          <td className="tiny muted" data-label="Wind">{windText(d, s.site_id, dd.date_ist)} · {s.models.join(', ')}</td>
                        </tr>
                      )))}
                    </tbody>
                  </table>
                </section>
              )}

              <Subscribe lon={answer.lon} lat={answer.lat} />
            </div>
          )}
        </section>

        <div className="home-scene">
          <Scene3D terrainId={`${city}-city`} view={view} summary={summary} interactive={!demo.active} smooth={demo.active ? 1.6 : 0.9}>
            {(frame) => (
              <>
                {citySites.map((s) => (
                  <group key={s.site_id}>
                    <Outline frame={frame} geom={s.polygon} width={1.6} step={40} />
                    <SiteLabel frame={frame} lon={s.centroid[0]} lat={s.centroid[1]} name={s.name} sub={siteSub(all ? Object.values(s.stats.fire_days_by_year).reduce((a, b) => a + b, 0) : s.stats.fire_days_by_year[year] ?? 0, all ? `${firstYear}–${d.data_through.slice(0, 4)}` : year)} />
                  </group>
                ))}
                <Columns frame={frame} dets={answer ? cityDets.filter((x) => x.counted) : cityDets.filter((x) => x.counted)} maxHeight={answer ? 700 : 1600}
                  dayOf={answer ? colDay : undefined} now={answer ? nowDay : undefined} />
                {answer && smokeSectors.map((s) => {
                  const o = sectorOpacity(dayIdx(s.date_ist), nowDay, player.p >= 1);
                  return o > 0 ? <SectorOutline key={s.site_id + s.date_ist} frame={frame} sector={s} opacity={o} /> : null;
                })}
                {answer && <Pin frame={frame} lon={answer.lon} lat={answer.lat} label={answer.label} pulse={pulse(res, nowDay, dayIdx)} />}
              </>
            )}
          </Scene3D>
          <p className="fig-cap"><span className="fig-no">Fig. 1.</span>{citySites[0]?.city_name ?? city}, Copernicus DEM GLO-30 (2011–2015, smoothed) contours every 4 m, every fifth line stronger (vertical exaggeration ×6); site outlines © OpenStreetMap; detections NASA FIRMS VIIRS; wind sectors modelled from Open-Meteo.</p>
        </div>
      </div>
      {!demo.active && <EmberLedger d={d} />}
    </main>
  );
}

function siteSub(n: number, span: string): string {
  return `${n} fire ${n === 1 ? 'day' : 'days'} ${span}`;
}

function sectorOpacity(day: number, now: number, done: boolean): number {
  if (done) return 0.32;
  if (day > now) return 0;
  return Math.max(0, 1 - (now - day) / 40);
}

function spanDays(a: string, b: string): number {
  return Math.round((Date.parse(b) - Date.parse(a)) / 86400000) + 1;
}

function calYears(res: DownwindResult): number[] {
  return [...new Set([...res.days, ...res.calm].map((x) => Number(x.date_ist.slice(0, 4))))].sort();
}

function pulse(res: DownwindResult | null, now: number, idx: (iso: string) => number): number {
  if (!res) return 0;
  for (const x of res.days) {
    const dd = idx(x.date_ist);
    if (now >= dd && now - dd < 4) return 1 - (now - dd) / 4;
  }
  return 0;
}

/** Nearest monitored landfill to a point outside coverage: distance from the point to the site, and which way the site lies. */
function nearestSite(d: Indexed, p: { label: string; lon: number; lat: number }) {
  const R = 6371, rad = Math.PI / 180;
  let best: { label: string; siteId: string; site: string; km: number; dir: string } | null = null;
  let bestKm = Infinity;
  for (const s of d.sites) {
    const [lon, lat] = s.centroid;
    const dLat = (lat - p.lat) * rad, dLon = (lon - p.lon) * rad;
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(p.lat * rad) * Math.cos(lat * rad) * Math.sin(dLon / 2) ** 2;
    const km = 2 * R * Math.asin(Math.sqrt(a));
    if (km < bestKm) {
      const y = Math.sin(dLon) * Math.cos(lat * rad), x = Math.cos(p.lat * rad) * Math.sin(lat * rad) - Math.sin(p.lat * rad) * Math.cos(lat * rad) * Math.cos(dLon);
      const brg = ((Math.atan2(y, x) / rad) + 360) % 360;
      bestKm = km;
      best = { label: p.label, siteId: s.site_id, site: s.name, km: Math.round(km), dir: COMPASS_WORDS[Math.round(brg / 45) % 8] };
    }
  }
  return best;
}

const COMPASS_WORDS = ['north', 'north-east', 'east', 'south-east', 'south', 'south-west', 'west', 'north-west'];

const COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

function windText(d: Indexed, siteId: string, date: string): string {
  const w = d.wind[siteId]?.[date];
  if (!w || w.length === 0) return 'no wind data';
  const dirs = [...new Set(w.map((h) => COMPASS[Math.round((((h.wd_from_deg % 360) + 360) % 360) / 22.5) % 16]))];
  const ws = w.map((h) => h.ws_ms);
  return `from ${dirs.join(', ')}, ${Math.min(...ws).toFixed(1)}–${Math.max(...ws).toFixed(1)} m/s`;
}
