import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import * as maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import 'maplibre-gl/dist/maplibre-gl.css';
// Production builds bundle MapLibre, so its default worker path (next to the module) does not exist: ship the worker as an asset.
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url';
import { useT } from '../i18n';
import { useSnapshot } from '../data/snapshot';
import { basemapStyle } from '../map/style';
import { TierChip } from '../components/Tier';
import { LiveStrip } from '../components/Chrome';
import { dateLabel, int, toIST } from '../lib/format';
import { webglAvailable } from '../three/Scene3D';
import { StillView } from '../three/StillView';
import { Frame, useTerrainData } from '../three/terrainData';
import './atlas.css';

let protocolAdded = false;

export function Atlas() {
  const { t, lang } = useT();
  const snap = useSnapshot();
  const d = snap.data;
  const [params, setParams] = useSearchParams();
  const city = params.get('city') ?? 'delhi';
  const nav = useNavigate();
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [hasTiles, setHasTiles] = useState<boolean | null>(null);
  const gl = useMemo(webglAvailable, []);
  const terr = useTerrainData(gl ? null : `${city}-city`);
  const planFrame = useMemo(() => (terr ? new Frame(terr) : null), [terr]);

  const cities = useMemo(() => (d ? [...new Set(d.sites.map((s) => s.city))] : []), [d]);
  const sites = useMemo(() => (d ? d.sites.filter((s) => s.city === city) : []), [d, city]);
  const through = d?.data_through ?? '';
  const recentCut = useMemo(() => (through ? new Date(Date.parse(through) - 364 * 86400000).toISOString().slice(0, 10) : ''), [through]);
  const weekCut = useMemo(() => (through ? new Date(Date.parse(through) - 6 * 86400000).toISOString().slice(0, 10) : ''), [through]);

  useEffect(() => {
    fetch(`/tiles/${city}.pmtiles`, { method: 'HEAD' }).then((r) => setHasTiles(r.ok && (r.headers.get('content-type') ?? '').indexOf('html') < 0)).catch(() => setHasTiles(false));
  }, [city]);

  useEffect(() => {
    if (!gl || !d || !box.current || hasTiles === null || sites.length === 0) return;
    if (!protocolAdded) { maplibregl.setWorkerUrl(workerUrl); maplibregl.addProtocol('pmtiles', new Protocol().tile); protocolAdded = true; }
    const lons = sites.flatMap((s) => [s.centroid[0]]), lats = sites.flatMap((s) => [s.centroid[1]]);
    const m = new maplibregl.Map({
      container: box.current,
      style: basemapStyle(hasTiles ? `${window.location.origin}/tiles/${city}.pmtiles` : null),
      bounds: [[Math.min(...lons) - 0.06, Math.min(...lats) - 0.05], [Math.max(...lons) + 0.06, Math.max(...lats) + 0.05]],
      attributionControl: { compact: true },
      dragRotate: false,
      pitchWithRotate: false,
    });
    map.current = m;
    m.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');
    m.on('load', () => {
      m.addSource('sites', { type: 'geojson', data: { type: 'FeatureCollection', features: sites.map((s) => ({ type: 'Feature', properties: { id: s.site_id }, geometry: s.polygon })) } });
      m.addLayer({ id: 'sites-line', type: 'line', source: 'sites', paint: { 'line-color': '#1F2B33', 'line-width': 1.6 } });
      m.addLayer({ id: 'sites-hit', type: 'fill', source: 'sites', paint: { 'fill-color': '#D2652F', 'fill-opacity': 0.08 } });
      const ids = new Set(sites.map((s) => s.site_id));
      const dets = d.detections.filter((x) => ids.has(x.site_id) && x.counted && x.date_ist >= recentCut);
      m.addSource('dets', { type: 'geojson', data: { type: 'FeatureCollection', features: dets.map((x) => ({ type: 'Feature', properties: { week: x.date_ist >= weekCut ? 1 : 0, frp: x.frp_mw ?? 1 }, geometry: { type: 'Point', coordinates: [x.lon, x.lat] } })) } });
      m.addLayer({ id: 'dets-year', type: 'circle', source: 'dets', filter: ['==', ['get', 'week'], 0], paint: { 'circle-radius': 3, 'circle-color': 'rgba(0,0,0,0)', 'circle-stroke-color': '#B8461B', 'circle-stroke-width': 1 } });
      m.addLayer({ id: 'dets-week', type: 'circle', source: 'dets', filter: ['==', ['get', 'week'], 1], paint: { 'circle-radius': 4, 'circle-color': '#F4C77A' } });
      m.on('click', 'sites-hit', (e: maplibregl.MapLayerMouseEvent) => { const id = e.features?.[0]?.properties?.id; if (id) nav(`/site/${id}`); });
      m.on('mouseenter', 'sites-hit', () => { m.getCanvas().style.cursor = 'pointer'; });
      m.on('mouseleave', 'sites-hit', () => { m.getCanvas().style.cursor = ''; });
      for (const s of sites) {
        const el = document.createElement('a');
        el.href = `/site/${s.site_id}`;
        el.className = 'map-label';
        el.textContent = s.name.toUpperCase();
        el.addEventListener('click', (ev) => { ev.preventDefault(); nav(`/site/${s.site_id}`); });
        new maplibregl.Marker({ element: el, anchor: 'left', offset: [14, 0] }).setLngLat(s.centroid).addTo(m);
      }
    });
    return () => { m.remove(); map.current = null; };
  }, [gl, d, sites, city, hasTiles, nav, recentCut, weekCut]);

  if (!d) return null;
  const ranked = [...d.sites].sort((a, b) => (a.rank.position ?? 99) - (b.rank.position ?? 99) || b.stats.fire_days_365 - a.stats.fire_days_365 || a.name.localeCompare(b.name));
  const rcfg = d.parameters.ranking as Record<string, number>;

  return (
    <main id="main" className="atlas">
      <LiveStrip />
      <div className="page atlas-head">
        <h1 className="serif">{t('atlas.title')}</h1>
        <div className="chip-row" role="tablist" aria-label="City">
          {cities.map((c) => <button key={c} role="tab" aria-selected={c === city} className={`tag${c === city ? ' tag-on' : ''}`} onClick={() => setParams({ city: c })}>{d.sites.find((s) => s.city === c)?.city_name}</button>)}
        </div>
      </div>
      {gl ? (
        <div className="atlas-map ticks" ref={box} role="img" aria-label={`Map of ${sites.map((s) => s.name).join(', ')} with counted detections of the last 365 days.`} />
      ) : (
        <div className="page atlas-plan">
          <p className="tiny muted">Interactive map unavailable (no WebGL); plan view of the same sites and detections.</p>
          {planFrame && <StillView frame={planFrame} drape={false} caption={`Plan of ${sites.map((s) => s.name).join(', ')}`}
            layers={{ polygons: sites.map((s) => ({ geom: s.polygon, kind: 'site' as const })), labels: sites.map((s) => ({ lon: s.centroid[0], lat: s.centroid[1], text: s.name })),
              dets: d.detections.filter((x) => sites.some((s) => s.site_id === x.site_id) && x.counted && x.date_ist >= recentCut) }} />}
        </div>
      )}
      <div className="page">
        <p className="fig-cap"><span className="fig-no">Fig. 1.</span>Site outlines (OSM; Brahmapuram traced from Sentinel-2). Filled dots: counted VIIRS detections in the 7 days to {dateLabel(through, lang)}; rings: the 365 days before. {hasTiles ? 'Basemap © OpenStreetMap contributors, Protomaps (self-hosted PMTiles).' : 'Basemap tiles not present in this build.'}</p>
        <div className="ledger-wrap">
          <table className="ledger atlas-ledger">
            <thead>
              <tr>
                <th>{t('atlas.rank')}</th><th>{t('atlas.site')}</th><th>{t('atlas.city')}</th>
                <th className="r">{t('atlas.firedays365')} <TierChip tier="MEASURED" /></th>
                <th>{t('atlas.last')}</th>
                <th className="r">{t('atlas.buildings')} <TierChip tier="COUNTED" /></th>
                <th className="r">{t('atlas.people')} <TierChip tier="ESTIMATED" /></th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((s) => (
                <tr key={s.site_id}>
                  <td className="num">{s.rank.position ?? <span className="tiny muted">{s.rank.label === 'no detections' ? t('atlas.nodet') : s.rank.label}</span>}</td>
                  <td><Link to={`/site/${s.site_id}`}>{s.name}</Link></td>
                  <td>{s.city_name}</td>
                  <td className="num r">{s.stats.fire_days_365 > 0 ? s.stats.fire_days_365 : <span className="tiny muted">{t('atlas.nodet')}</span>}</td>
                  <td className="num">{s.stats.last_detection_utc ? `${dateLabel(toIST(s.stats.last_detection_utc).date, lang)} ${toIST(s.stats.last_detection_utc).time}` : '—'}</td>
                  <td className="num r">{int(s.context?.buildings_1km)}</td>
                  <td className="num r">{s.context ? `~${int(Math.round(s.context.people_1km_est / 1000) * 1000)}` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small" data-metric>
          {t('atlas.formula')}: <span className="mono">score = fire_days_last_365^{rcfg.w_fire} × log10(1 + people_1km_est)^{rcfg.w_people}</span>. Sites with no counted detections in the last 365 days are listed as “no detections”, not ranked. <TierChip tier="MODELLED" />
          <span className="tiny muted" data-receipt> Fire days: NASA FIRMS (MEASURED). People: WorldPop 2020 (ESTIMATED). Last 365 days to {through}.</span>
        </p>
      </div>
    </main>
  );
}
