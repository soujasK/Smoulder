import { useEffect, useRef, useState } from 'react';
import type { BurnObs, Site } from '../types/contract';
import { Metric } from './Tier';
import { dateLabel } from '../lib/format';
import { useReducedMotion } from '../three/Scene3D';
import { API_BASE_URL, DATA_MODE } from '../config';

// In live mode crops come from the API (presigned S3); offline they are bundled under /imagery.
const img = (p?: string) => (p && DATA_MODE === 'live' && API_BASE_URL ? `${API_BASE_URL}${p}` : p);

/** Sentinel-2 SWIR false colour with the measured mask revealed by a scan line; pre/post slider. */
export function BurnScan({ site, obs }: { site: Site; obs: BurnObs[] }) {
  const episodes = [...new Set(obs.map((o) => o.episode_start))].sort().reverse();
  const [ep, setEp] = useState<string | null>(null);
  const cur = ep ?? episodes.find((e) => obs.some((o) => o.episode_start === e && o.kind === 'post' && o.area_ha !== null)) ?? episodes[0] ?? null;
  const post = obs.find((o) => o.episode_start === cur && o.kind === 'post');
  const pre = obs.find((o) => o.episode_start === cur && o.kind === 'pre');
  return (
    <section className="sec">
      <div className="sec-head"><span className="sec-no">04</span><h2>Burn Scan</h2></div>
      {episodes.length === 0 ? (
        <p className="small muted">Burn Scan has not been run for {site.name}, or no episode had a clear Sentinel-2 scene.</p>
      ) : (
        <>
          <div className="chip-row" role="tablist" aria-label="Episode">
            {episodes.map((e) => <button key={e} role="tab" aria-selected={e === cur} className={`tag${e === cur ? ' tag-on' : ''}`} onClick={() => setEp(e)}>{dateLabel(e)}</button>)}
          </div>
          {post && post.area_ha !== null && pre ? <Scan pre={pre} post={post} /> : <p className="small muted">{post?.note ?? pre?.note ?? 'No clear image for this episode.'}</p>}
        </>
      )}
    </section>
  );
}

function Scan({ pre, post }: { pre: BurnObs; post: BurnObs }) {
  const reduced = useReducedMotion();
  const [reveal, setReveal] = useState(reduced ? 1 : 0);
  const [split, setSplit] = useState(0.5);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (reduced) { setReveal(1); return; }
    let raf = 0;
    const el = ref.current;
    const start = () => {
      const t0 = performance.now();
      const tick = (t: number) => { const v = Math.min(1, (t - t0) / 2400); setReveal(v); if (v < 1) raf = requestAnimationFrame(tick); };
      raf = requestAnimationFrame(tick);
    };
    const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) { start(); io.disconnect(); } }, { threshold: 0.4 });
    if (el) io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [reduced, post.scene_date]);
  const shown = (post.area_ha ?? 0) * reveal;
  return (
    <div className="burn" ref={ref}>
      <div className="burn-imgs ticks">
        <img src={img(post.crops.swir)} alt={`Sentinel-2 SWIR false colour after the episode, ${post.scene_date}`} />
        <div className="burn-pre" style={{ clipPath: `inset(0 ${100 - split * 100}% 0 0)` }}>
          <img src={img(pre.crops.swir)} alt={`Sentinel-2 SWIR false colour before the episode, ${pre.scene_date}`} />
        </div>
        <img className="burn-mask" src={img(post.crops.mask)} alt="" style={{ clipPath: `inset(0 0 ${100 - reveal * 100}% 0)` }} />
        <div className="burn-scanline" style={{ top: `${reveal * 100}%`, opacity: reveal < 1 ? 1 : 0 }} />
        <div className="burn-split" style={{ left: `${split * 100}%` }} />
        <span className="burn-tag mono tiny" style={{ left: 6 }}>PRE {pre.scene_date}</span>
        <span className="burn-tag mono tiny" style={{ right: 6 }}>POST {post.scene_date}</span>
      </div>
      <label className="burn-slider">
        <span className="sr-only">Before / after</span>
        <input type="range" min={0} max={1} step={0.01} value={split} onChange={(e) => setSplit(Number(e.target.value))} />
      </label>
      <div className="metrics">
        <Metric label="Burn-like change inside the boundary (dNBR)" value={shown.toFixed(1)} unit={`ha (${post.area_ha_lo?.toFixed(1)}–${post.area_ha_hi?.toFixed(1)})`} tier="MEASURED"
          receipt={{ source: `Sentinel-2 L2A ${pre.scene_date} → ${post.scene_date} (Copernicus, AWS Open Data)`, method: 'dNBR = NBR_pre − NBR_post on 20 m B8A/B12, mask where dNBR > threshold; range ± half the boundary pixels', date: post.scene_date, href: '/method#burn-scan' }} />
        <Metric label="Hot-surface pixels (heuristic)" value={post.hot_px ?? 0} unit="pixels, 20 m" tier="MEASURED"
          receipt={{ source: `Sentinel-2 L2A ${post.scene_date}`, method: 'B12 above threshold and B12 > B11 > B8A (heuristic)', date: post.scene_date, href: '/method#burn-scan' }} />
      </div>
      <p className="fig-cap"><span className="fig-no">Fig. 3.</span>Sentinel-2 L2A SWIR composite (B12, B8A, B4), 20 m, linear 2–98% stretch, no sharpening. Ember mask: dNBR burn pixels inside the boundary. {post.note} Contains modified Copernicus Sentinel data.</p>
    </div>
  );
}
