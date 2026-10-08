import { useEffect, useMemo } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { useSnapshot } from '../data/snapshot';
import { useT } from '../i18n';
import { Calendar, type CellKind } from '../components/Calendar';
import { TierChip } from '../components/Tier';
import { Limits } from '../components/Limits';
import { StillView } from '../three/StillView';
import { Frame, useTerrainData } from '../three/terrainData';
import { dateLabel, fixed, int, km, toIST } from '../lib/format';
import type { MetricTier } from '../types/contract';
import './print.css';

function Row({ k, v, tier, src }: { k: string; v: string; tier: MetricTier; src: string }) {
  return <tr data-metric><td>{k}</td><td className="num r">{v}</td><td><TierChip tier={tier} /></td><td className="tiny" data-receipt>{src}</td></tr>;
}

function Sheet({ children, title, recno, coords }: { children: React.ReactNode; title: string; recno: string; coords: string }) {
  const snap = useSnapshot();
  useEffect(() => { document.title = `${title} · Smoulder`; }, [title]);
  return (
    <div className="print-shell" data-surface="paper">
      <div className="print-toolbar no-print">
        <Link to={-1 as unknown as string} onClick={(e) => { e.preventDefault(); history.back(); }}>← Back</Link>
        <button className="btn" onClick={() => window.print()}>Print / save PDF</button>
      </div>
      <article className="a4">
        <span className="crop tl" /><span className="crop tr" /><span className="crop bl" /><span className="crop br" />
        <span className="reg reg-t" /><span className="reg reg-b" />
        <header className="a4-mast">
          <span className="a4-word">SMOULDER</span>
          <span className="mono tiny">{recno}</span>
          <span className="mono tiny">{coords}</span>
        </header>
        {children}
        <footer className="a4-foot mono tiny">
          <span>Generated {snap.data?.generated_at.slice(0, 10)} · run {snap.data?.pipeline_run_id} · data through {snap.data?.data_through}</span>
          <span>NASA FIRMS · Open-Meteo · Copernicus Sentinel-2 & DEM · © OpenStreetMap contributors · WorldPop</span>
        </footer>
      </article>
    </div>
  );
}

export function PrintSite() {
  const { id = '' } = useParams();
  const [params] = useSearchParams();
  const { lang } = useT();
  const snap = useSnapshot();
  const d = snap.data;
  const site = d?.siteById[id];
  const terr = useTerrainData(site ? `${site.city}-city` : null);
  const frame = useMemo(() => (terr ? new Frame(terr) : null), [terr]);
  if (!d || !site) return null;
  const fds = d.fdBySite[id] ?? [];
  const ys = Object.entries(site.stats.fire_days_by_year).filter(([, n]) => n > 0).map(([y]) => y).sort();
  const year = params.get('year') ?? ys[ys.length - 1] ?? String(Number(d.data_through.slice(0, 4)) - 1);
  const cells: Record<string, CellKind> = {};
  for (const f of fds) if (f.date_ist.startsWith(year)) cells[f.date_ist] = 'fill';
  const ticks = new Set(d.validation.events.filter((e) => e.site_id === id).map((e) => e.date_start));
  const ctx = site.context;
  const brief = d.briefs.find((b) => b.site_id === id && b.lang === lang) ?? d.briefs.find((b) => b.site_id === id);
  const idx = d.sites.findIndex((s) => s.site_id === id) + 1;
  const eps = d.epBySite[id] ?? [];
  const firms = 'NASA FIRMS VIIRS';
  return (
    <Sheet title={`${site.name} Fire Record`} recno={`FIRE RECORD ${String(idx).padStart(2, '0')} / ${String(d.sites.length).padStart(2, '0')}`} coords={`${site.centroid[1].toFixed(4)}°N ${site.centroid[0].toFixed(4)}°E · ${site.area_ha} ha · ${site.boundary_source}`}>
      <h1 className="a4-title serif">{site.name} <span className="a4-sub">{site.city_name}</span></h1>
      <div className="a4-grid">
        <section>
          <h2 className="a4-h">Record</h2>
          <table className="a4-table">
            <tbody>
              <Row k={`Fire days, ${year}`} v={String(fds.filter((f) => f.date_ist.startsWith(year)).length)} tier="MEASURED" src={firms} />
              <Row k="Fire days, all years" v={String(fds.length)} tier="MEASURED" src={firms} />
              <Row k="Fire days, last 365 d" v={String(site.stats.fire_days_365)} tier="MEASURED" src={firms} />
              <Row k="Episodes" v={String(eps.length)} tier="MEASURED" src="gap ≤ 1 day" />
              <Row k="Max FRP (MW)" v={fixed(site.stats.max_frp_mw)} tier="MEASURED" src={firms} />
              <Row k="Last counted detection" v={site.stats.last_detection_utc ? `${dateLabel(toIST(site.stats.last_detection_utc).date)}` : '—'} tier="MEASURED" src={firms} />
              {ctx && <>
                <Row k="Buildings within 1 km" v={int(ctx.buildings_1km)} tier="COUNTED" src={`OSM, ${ctx.retrieved_on}`} />
                <Row k="Schools within 1 / 3 km" v={`${ctx.schools_1km} / ${ctx.schools_3km}`} tier="COUNTED" src={`OSM, ${ctx.retrieved_on}`} />
                <Row k="Nearest school" v={ctx.nearest_school_m !== null ? km(ctx.nearest_school_m) : '—'} tier="COUNTED" src="OSM" />
                <Row k="People within 1 km" v={`~${int(Math.round(ctx.people_1km_est / 1000) * 1000)}`} tier="ESTIMATED" src="WorldPop 2020" />
              </>}
              {site.schools_downwind && <Row k={`Schools downwind on a fire day, ${site.schools_downwind.year}`} v={`${site.schools_downwind.schools_downwind_any_day} / ${site.schools_downwind.schools_considered}`} tier="MODELLED" src="Open-Meteo wind, downwind rule" />}
            </tbody>
          </table>
          <p className="tiny">Satellite period {site.stats.first_data_date} to {site.stats.data_through}; Tier A/B, nominal or high confidence.</p>
          <h2 className="a4-h">Fire days by year</h2>
          <table className="a4-table"><tbody>{Object.entries(site.stats.fire_days_by_year).map(([y, n]) => <tr key={y}><td className="num">{y}</td><td className="num r">{n > 0 ? n : <span className="tiny">no detections</span>}</td></tr>)}</tbody></table>
        </section>
        <section>
          <h2 className="a4-h">Calendar {year}</h2>
          <Calendar year={Number(year)} cells={cells} ticks={ticks} caption={`${site.name} ${year}`} legend={{ fill: 'fire day (A/B)', tick: 'news-reported' }} through={d.data_through} />
          <h2 className="a4-h">Downwind sectors {year}</h2>
          {frame && <StillView frame={frame} paper drape={false} layers={{ polygons: d.sites.filter((s) => s.city === site.city).map((s) => ({ geom: s.polygon, kind: 'site' as const })), sectors: d.sectors.filter((s) => s.site_id === id && s.date_ist.startsWith(year)), labels: [{ lon: site.centroid[0], lat: site.centroid[1], text: site.name }] }} />}
          <p className="tiny">Thin lines: modelled downwind sectors (R {String((d.parameters.downwind as Record<string, number>).radius_km)} km) on {year} fire days. MODELLED.</p>
        </section>
      </div>
      {brief && <section><h2 className="a4-h">Brief · {brief.label}</h2><p className="a4-brief serif" lang={brief.lang}>{brief.text}</p></section>}
      <section className="a4-limits"><Limits /></section>
    </Sheet>
  );
}

export function PrintSmoke() {
  const [params] = useSearchParams();
  const snap = useSnapshot();
  const d = snap.data;
  const lm = d?.landmarks.find((l) => l.id === params.get('lm')) ?? d?.landmarks[0];
  const year = params.get('year') ?? 'all';
  if (!d || !lm) return null;
  const r = lm.results[year];
  const cells: Record<string, CellKind> = {};
  for (const x of r.days) cells[x.date_ist] = 'fill';
  const years = year === 'all' ? [...new Set(r.days.map((x) => Number(x.date_ist.slice(0, 4))))].sort() : [Number(year)];
  return (
    <Sheet title={`Smoke Days ${lm.name}`} recno="SMOKE DAYS SHEET" coords={`${lm.lat.toFixed(3)}°N ${lm.lon.toFixed(3)}°E`}>
      <h1 className="a4-title serif">{lm.name}</h1>
      <p className="a4-lede serif" data-metric>{year === 'all' ? `From ${d.sites[0].stats.first_data_date.slice(0, 4)} to ${dateLabel(d.data_through)}` : `In ${year}`}, this place was downwind of a detected landfill fire on <b className="num">{r.smoke_days}</b> days. <TierChip tier="MODELLED" /><span className="tiny" data-receipt> Rule: ±{r.parameters.half_width_deg}°, ≥{r.parameters.min_hours} h in {r.parameters.window_hours} h after first detection, wind ≥{r.parameters.ws_min_ms} m/s, R {r.parameters.radius_km} km.</span></p>
      <table className="a4-table"><thead><tr><th>Site</th><th className="r">Distance</th><th>Direction</th><th className="r">Fire days</th></tr></thead>
        <tbody>{r.nearest_sites.map((n) => <tr key={n.site_id}><td>{n.name}</td><td className="num r">{km(n.distance_m)}</td><td>{n.bearing_compass}</td><td className="num r">{n.fire_days}</td></tr>)}</tbody></table>
      {years.map((y) => <div key={y}><h2 className="a4-h">{y}</h2><Calendar year={y} cells={cells} caption={String(y)} legend={{ fill: 'smoke day (modelled)' }} through={d.data_through} /></div>)}
      <table className="a4-table"><thead><tr><th>Date</th><th>Site</th><th className="r">Downwind hours</th><th>Wind model</th></tr></thead>
        <tbody>{r.days.flatMap((x) => x.sites.map((s) => <tr key={x.date_ist + s.site_id}><td className="num">{dateLabel(x.date_ist)}</td><td>{s.name}</td><td className="num r">{s.downwind_hours}/{r.parameters.window_hours}</td><td className="tiny">{s.models.join(', ')}</td></tr>))}</tbody></table>
      <section className="a4-limits"><Limits /></section>
    </Sheet>
  );
}
