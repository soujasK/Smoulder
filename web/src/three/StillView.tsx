import { useMemo } from 'react';
import type { Frame } from './terrainData';
import { polygonRings } from './terrainData';
import { frpColor } from './colors';
import type { Detection, Sector } from '../types/contract';

const hillCache = new Map<string, string>();

/** Hillshade + contour raster of the heightmap, rendered once per tile to a data URL. */
function hillshade(frame: Frame, paper: boolean): string {
  const key = frame.t.id + (paper ? ':p' : ':d');
  const hit = hillCache.get(key);
  if (hit) return hit;
  const { px, res_m, contour_interval_m } = frame.t.meta;
  const H = frame.t.heights;
  const c = document.createElement('canvas');
  c.width = px; c.height = px;
  const ctx = c.getContext('2d');
  if (!ctx) return '';
  const img = ctx.createImageData(px, px);
  const base = paper ? [242, 238, 228] : [234, 236, 231];
  const line = paper ? [204, 197, 182] : [200, 206, 204];
  const major = paper ? [140, 143, 138] : [128, 141, 147];
  const ve = 3;
  for (let j = 0; j < px; j++) {
    for (let i = 0; i < px; i++) {
      const k = j * px + i;
      const l = H[j * px + Math.max(0, i - 1)], r = H[j * px + Math.min(px - 1, i + 1)];
      const u = H[Math.max(0, j - 1) * px + i], d = H[Math.min(px - 1, j + 1) * px + i];
      const dx = ((r - l) * ve) / (2 * res_m), dy = ((d - u) * ve) / (2 * res_m);
      const shade = Math.max(0, Math.min(1, 0.75 + (-dx * 0.6 + dy * 0.4)));
      let col = base.map((v) => v * (0.92 + 0.08 * shade));
      const f = H[k] / contour_interval_m;
      const fl = Math.floor(f);
      const neigh = [l, r, u, d].some((h) => Math.floor(h / contour_interval_m) !== fl);
      if (neigh) col = (fl % 5 === 0 ? major : line).slice();
      img.data.set([col[0], col[1], col[2], 255], k * 4);
    }
  }
  ctx.putImageData(img, 0, 0);
  const url = c.toDataURL('image/png');
  hillCache.set(key, url);
  return url;
}

export interface PlanLayers {
  polygons?: { geom: GeoJSON.Polygon | GeoJSON.MultiPolygon; kind: 'site' | 'ring' }[];
  dets?: Detection[];
  sectors?: Sector[];
  pin?: { lon: number; lat: number; label?: string } | null;
  footprints?: Detection[];
  labels?: { lon: number; lat: number; text: string }[];
}

/** North-up SVG plan of a terrain tile with the same overlays as the 3D scene. */
export function StillView({ frame, layers = {}, paper = false, drape = true, caption }: { frame: Frame; layers?: PlanLayers; paper?: boolean; drape?: boolean; caption?: string }) {
  const half = frame.half;
  const bg = useMemo(() => hillshade(frame, paper), [frame, paper]);
  const path = (ring: number[][]) => ring.map((p, i) => { const [x, z] = frame.xz(p[0], p[1]); return `${i ? 'L' : 'M'}${x.toFixed(1)},${z.toFixed(1)}`; }).join('') + 'Z';
  const [w, s, e, n] = frame.t.meta.bounds_wgs84;
  const step = frame.t.meta.extent_m > 10000 ? 0.1 : 0.01;
  const ticks: { x: number; z: number; label: string; edge: 'top' | 'left' }[] = [];
  for (let lon = Math.ceil(w / step) * step; lon <= e; lon += step) { const [x] = frame.xz(lon, (s + n) / 2); if (Math.abs(x) < half) ticks.push({ x, z: -half, label: lon.toFixed(step < 0.05 ? 2 : 1) + '°E', edge: 'top' }); }
  for (let lat = Math.ceil(s / step) * step; lat <= n; lat += step) { const [, z] = frame.xz((w + e) / 2, lat); if (Math.abs(z) < half) ticks.push({ x: -half, z, label: lat.toFixed(step < 0.05 ? 2 : 1) + '°N', edge: 'left' }); }
  const sb = frame.t.meta.extent_m > 10000 ? 5000 : 500;
  const ink = paper ? '#141414' : '#1F2B33';
  const fs = frame.t.meta.extent_m / 60;
  return (
    <figure className="fig" style={{ margin: 0 }}>
      <svg viewBox={`${-half} ${-half} ${2 * half} ${2 * half}`} width="100%" role="img" aria-label={caption ?? 'Plan view'} style={{ display: 'block', background: paper ? '#F2EEE4' : '#EAECE7', borderRadius: paper ? 0 : 14 }}>
        <image href={bg} x={-half} y={-half} width={2 * half} height={2 * half} preserveAspectRatio="none" style={{ imageRendering: 'auto' }} />
        {drape && frame.t.drapeUrl && <image href={frame.t.drapeUrl} x={-half} y={-half} width={2 * half} height={2 * half} opacity={paper ? 0.35 : 0.22} preserveAspectRatio="none" />}
        {layers.sectors?.map((sec, i) => polygonRings(sec.geometry).map((r, j) => <path key={`s${i}-${j}`} d={path(r)} fill="none" stroke="#4C7C9E" strokeWidth={fs / 12} />))}
        {layers.polygons?.map((p, i) => polygonRings(p.geom).map((r, j) => (
          <path key={`p${i}-${j}`} d={path(r)} fill="none" stroke={p.kind === 'site' ? ink : paper ? '#4B4B47' : '#7E8C93'} strokeWidth={p.kind === 'site' ? fs / 8 : fs / 14} strokeDasharray={p.kind === 'ring' ? `${fs / 2} ${fs / 2}` : undefined} />
        )))}
        {layers.footprints?.map((d) => { const [x, z] = frame.xz(d.lon, d.lat); const hw = ((d.scan_km ?? 0.375) * 1000) / 2, hh = ((d.track_km ?? 0.375) * 1000) / 2; return <rect key={`f${d.det_id}`} x={x - hw} y={z - hh} width={2 * hw} height={2 * hh} fill="none" stroke="#B8461B" strokeWidth={fs / 12} />; })}
        {layers.dets?.map((d) => { const [x, z] = frame.xz(d.lon, d.lat); return <circle key={d.det_id} cx={x} cy={z} r={fs / 4} fill={d.counted ? frpColor(d.frp_mw) : 'none'} stroke={d.counted ? 'none' : '#7E8C93'} strokeWidth={fs / 16} />; })}
        {layers.pin && (() => { const [x, z] = frame.xz(layers.pin.lon, layers.pin.lat); return <g><circle cx={x} cy={z} r={fs / 2.5} fill="none" stroke={ink} strokeWidth={fs / 10} /><circle cx={x} cy={z} r={fs / 10} fill={ink} />{layers.pin.label && <text x={x + fs / 1.5} y={z} fontSize={fs} fill={ink} fontFamily="JetBrains Mono Variable, monospace" dominantBaseline="middle">{layers.pin.label}</text>}</g>; })()}
        {layers.labels?.map((l, i) => { const [x, z] = frame.xz(l.lon, l.lat); return <text key={`l${i}`} x={x} y={z - fs * 0.8} fontSize={fs * 0.9} fill={ink} textAnchor="middle" fontFamily="Archivo Variable, sans-serif" letterSpacing={fs * 0.08}>{l.text.toUpperCase()}</text>; })}
        {ticks.map((t, i) => t.edge === 'top'
          ? <g key={`t${i}`}><line x1={t.x} x2={t.x} y1={-half} y2={-half + fs * 0.6} stroke={ink} strokeWidth={fs / 16} /><text x={t.x + fs * 0.2} y={-half + fs * 1.4} fontSize={fs * 0.7} fill={ink} fontFamily="JetBrains Mono Variable, monospace" opacity={0.8}>{t.label}</text></g>
          : <g key={`t${i}`}><line x1={-half} x2={-half + fs * 0.6} y1={t.z} y2={t.z} stroke={ink} strokeWidth={fs / 16} /><text x={-half + fs * 0.8} y={t.z - fs * 0.2} fontSize={fs * 0.7} fill={ink} fontFamily="JetBrains Mono Variable, monospace" opacity={0.8}>{t.label}</text></g>)}
        <g transform={`translate(${half - fs * 9}, ${half - fs * 2})`}>
          <line x1={0} x2={(sb / (2 * half)) * 2 * half} y1={0} y2={0} stroke={ink} strokeWidth={fs / 10} />
          <line x1={0} x2={0} y1={-fs * 0.4} y2={0} stroke={ink} strokeWidth={fs / 12} />
          <line x1={sb} x2={sb} y1={-fs * 0.4} y2={0} stroke={ink} strokeWidth={fs / 12} />
          <text x={0} y={-fs * 0.7} fontSize={fs * 0.75} fill={ink} fontFamily="JetBrains Mono Variable, monospace">{sb >= 1000 ? `${sb / 1000} km` : `${sb} m`}</text>
        </g>
        <g transform={`translate(${half - fs * 2}, ${-half + fs * 3})`}>
          <line x1={0} x2={0} y1={fs * 1.2} y2={-fs * 1.2} stroke={ink} strokeWidth={fs / 12} />
          <polyline points={`${-fs * 0.5},${-fs * 0.5} 0,${-fs * 1.2} ${fs * 0.5},${-fs * 0.5}`} fill="none" stroke={ink} strokeWidth={fs / 12} />
          <text x={0} y={fs * 2.2} fontSize={fs * 0.8} fill={ink} textAnchor="middle" fontFamily="JetBrains Mono Variable, monospace">N</text>
        </g>
      </svg>
      {caption && <figcaption className="fig-cap">{caption}</figcaption>}
    </figure>
  );
}
