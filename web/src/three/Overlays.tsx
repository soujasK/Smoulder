import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { Html, Line } from '@react-three/drei';
import type { Frame } from './terrainData';
import { polygonRings } from './terrainData';
import { COLORS, frpColor, frpScale } from './colors';
import type { Detection, Sector } from '../types/contract';

/** Densify a lon/lat ring into scene points draped on the terrain. */
function drape(frame: Frame, ring: number[][], step: number, lift: number): [number, number, number][] {
  const pts: [number, number, number][] = [];
  for (let i = 0; i < ring.length - 1; i++) {
    const [x0, z0] = frame.xz(ring[i][0], ring[i][1]);
    const [x1, z1] = frame.xz(ring[i + 1][0], ring[i + 1][1]);
    const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, z1 - z0) / step));
    for (let k = 0; k < n; k++) {
      const x = x0 + ((x1 - x0) * k) / n, z = z0 + ((z1 - z0) * k) / n;
      pts.push([x, frame.yAt(x, z, lift), z]);
    }
  }
  const [xe, ze] = frame.xz(ring[ring.length - 1][0], ring[ring.length - 1][1]);
  pts.push([xe, frame.yAt(xe, ze, lift), ze]);
  return pts;
}

export function Outline({ frame, geom, color = COLORS.bone, width = 1.4, dashed = false, step = 25, lift = 3, opacity = 1 }: {
  frame: Frame; geom: GeoJSON.Polygon | GeoJSON.MultiPolygon; color?: string; width?: number; dashed?: boolean; step?: number; lift?: number; opacity?: number;
}) {
  const rings = useMemo(() => polygonRings(geom).map((r) => drape(frame, r, step, lift * frame.ve)), [frame, geom, step, lift]);
  return (
    <>
      {rings.map((pts, i) => (
        <Line key={i} points={pts} color={color} lineWidth={width} dashed={dashed} dashSize={dashed ? 60 : undefined} gapSize={dashed ? 50 : undefined} transparent opacity={opacity} />
      ))}
    </>
  );
}

/** Thin ember columns, one per detection; height and colour from FRP (log scale).
 *  Static geometry; `now` (a day index) animates growth in the shader, so nothing is rebuilt per frame. */
export function Columns({ frame, dets, dayOf, now, maxHeight }: {
  frame: Frame; dets: Detection[]; dayOf?: (d: Detection) => number; now?: number; maxHeight: number;
}) {
  const geom = useMemo(() => {
    const pos: number[] = [], col: number[] = [], day: number[] = [], top: number[] = [], hgt: number[] = [];
    const c = new THREE.Color();
    for (const d of dets) {
      const [x, z] = frame.xz(d.lon, d.lat);
      if (!frame.inside(x, z)) continue;
      const y0 = frame.yAt(x, z, 1);
      const h = (0.25 + 0.75 * frpScale(d.frp_mw)) * maxHeight;
      const k = d.counted ? 1 : 0.55;
      c.set(d.counted ? frpColor(d.frp_mw) : COLORS.ash);
      const dd = dayOf ? dayOf(d) : 0;
      pos.push(x, y0, z, x, y0, z);
      col.push(c.r * k * 0.55, c.g * k * 0.55, c.b * k * 0.55, c.r * k, c.g * k, c.b * k);
      day.push(dd, dd); top.push(0, 1); hgt.push(h, h);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
    g.setAttribute('aDay', new THREE.Float32BufferAttribute(day, 1));
    g.setAttribute('aTop', new THREE.Float32BufferAttribute(top, 1));
    g.setAttribute('aH', new THREE.Float32BufferAttribute(hgt, 1));
    g.computeBoundingSphere();
    if (g.boundingSphere) g.boundingSphere.radius += maxHeight;
    return g;
  }, [frame, dets, dayOf, maxHeight]);
  const mat = useMemo(() => new THREE.ShaderMaterial({
    transparent: true,
    vertexColors: true,
    uniforms: { uNow: { value: 1e9 } },
    vertexShader: `
      attribute float aDay; attribute float aTop; attribute float aH;
      uniform float uNow; varying vec3 vC; varying float vA;
      void main() {
        vC = color;
        float age = uNow - aDay;
        float g = age < 0.0 ? 0.0 : clamp(age / 6.0 + 0.15, 0.0, 1.0);
        vA = age < 0.0 ? 0.0 : 0.95;
        vec3 p = position + vec3(0.0, aTop * aH * g, 0.0);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }`,
    fragmentShader: `
      varying vec3 vC; varying float vA;
      void main() {
        if (vA <= 0.0) discard;
        gl_FragColor = vec4(vC, vA);
        #include <colorspace_fragment>
      }`,
  }), []);
  useEffect(() => () => { geom.dispose(); }, [geom]);
  useEffect(() => () => { mat.dispose(); }, [mat]);
  mat.uniforms.uNow.value = now ?? 1e9;
  return <lineSegments geometry={geom} material={mat} />;
}

/** Ground squares (pixel centres) under each detection, small and flat. */
export function Footprint({ frame, det, color = COLORS.ember5, label }: { frame: Frame; det: Detection; color?: string; label?: string }) {
  const scan = det.scan_km ?? 0.375, track = det.track_km ?? 0.375;
  const [x, z] = frame.xz(det.lon, det.lat);
  const hw = (scan * 1000) / 2, hh = (track * 1000) / 2;
  const corners: [number, number][] = [[x - hw, z - hh], [x + hw, z - hh], [x + hw, z + hh], [x - hw, z + hh], [x - hw, z - hh]];
  const pts: [number, number, number][] = [];
  for (let i = 0; i < 4; i++) {
    const [x0, z0] = corners[i], [x1, z1] = corners[i + 1];
    for (let k = 0; k < 20; k++) {
      const xx = x0 + ((x1 - x0) * k) / 20, zz = z0 + ((z1 - z0) * k) / 20;
      pts.push([xx, frame.yAt(xx, zz, 4 * frame.ve), zz]);
    }
  }
  pts.push(pts[0]);
  const y = frame.yAt(x, z, 4 * frame.ve);
  return (
    <group>
      <Line points={pts} color={color} lineWidth={1.6} />
      <mesh position={[x, y, z]} rotation={[-Math.PI / 2, 0, 0]}>
        <circleGeometry args={[9, 16]} />
        <meshBasicMaterial color={color} />
      </mesh>
      {label && (
        <Html position={[x + hw, y, z - hh]} style={{ pointerEvents: 'none' }}>
          <div className="scene-label mono">{label}</div>
        </Html>
      )}
    </group>
  );
}

/** Wind sector wedge outline: thin lines only, no fill. */
export function SectorOutline({ frame, sector, opacity = 1 }: { frame: Frame; sector: Sector; opacity?: number }) {
  return <Outline frame={frame} geom={sector.geometry} color={COLORS.wind} width={1} step={80} lift={14} opacity={opacity} />;
}

export function Pin({ frame, lon, lat, label, pulse = 0 }: { frame: Frame; lon: number; lat: number; label?: string; pulse?: number }) {
  const [x, z] = frame.xz(lon, lat);
  const y0 = frame.yAt(x, z, 0);
  const h = Math.max(120, Math.min(320, frame.t.meta.extent_m / 120));
  return (
    <group>
      <Line points={[[x, y0, z], [x, y0 + h, z]]} color={COLORS.bone} lineWidth={1.2} />
      <mesh position={[x, y0 + h, z]}>
        <octahedronGeometry args={[h / 14 * (1 + pulse * 0.6), 0]} />
        <meshBasicMaterial color={pulse > 0 ? COLORS.ember5 : COLORS.bone} wireframe />
      </mesh>
      {label && (
        <Html position={[x, y0 + h * 1.15, z]} center style={{ pointerEvents: 'none' }}>
          <div className="scene-label scene-label-pin">{label}</div>
        </Html>
      )}
    </group>
  );
}

export function SiteLabel({ frame, lon, lat, name, sub }: { frame: Frame; lon: number; lat: number; name: string; sub?: string }) {
  const [x, z] = frame.xz(lon, lat);
  return (
    <Html position={[x, frame.yAt(x, z, 40), z]} style={{ pointerEvents: 'none' }}>
      <div className="scene-label scene-label-site"><span>{name}</span>{sub && <span className="mono">{sub}</span>}</div>
    </Html>
  );
}

/** Coordinate graticule draped on the terrain with mono labels at the north and west edges. */
export function Graticule({ frame, stepDeg }: { frame: Frame; stepDeg: number }) {
  const lines = useMemo(() => {
    const [w, s, e, n] = frame.t.meta.bounds_wgs84;
    const out: { pts: [number, number, number][]; label: string; at: [number, number, number] }[] = [];
    const fmt = (v: number) => v.toFixed(stepDeg < 0.05 ? 2 : 1) + '°';
    for (let lon = Math.ceil(w / stepDeg) * stepDeg; lon <= e; lon += stepDeg) {
      const pts: [number, number, number][] = [];
      for (let i = 0; i <= 60; i++) {
        const lat = s + ((n - s) * i) / 60;
        const [x, z] = frame.xz(lon, lat);
        if (frame.inside(x, z)) pts.push([x, frame.yAt(x, z, 1), z]);
      }
      if (pts.length > 1) out.push({ pts, label: fmt(lon) + 'E', at: pts[pts.length - 1] });
    }
    for (let lat = Math.ceil(s / stepDeg) * stepDeg; lat <= n; lat += stepDeg) {
      const pts: [number, number, number][] = [];
      for (let i = 0; i <= 60; i++) {
        const lon = w + ((e - w) * i) / 60;
        const [x, z] = frame.xz(lon, lat);
        if (frame.inside(x, z)) pts.push([x, frame.yAt(x, z, 1), z]);
      }
      if (pts.length > 1) out.push({ pts, label: fmt(lat) + 'N', at: pts[0] });
    }
    return out;
  }, [frame, stepDeg]);
  return (
    <>
      {lines.map((l, i) => (
        <group key={i}>
          <Line points={l.pts} color={COLORS.ruleDarkLift} lineWidth={0.8} transparent opacity={0.7} />
          <Html position={l.at} style={{ pointerEvents: 'none' }}>
            <div className="scene-grat mono">{l.label}</div>
          </Html>
        </group>
      ))}
    </>
  );
}
