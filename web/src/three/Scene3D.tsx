import { Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { CameraControls } from '@react-three/drei';
import * as THREE from 'three';
import { Frame, loadTerrain, type TerrainData } from './terrainData';
import { TerrainMesh } from './Terrain';
import { COLORS } from './colors';
import { StillView } from './StillView';
import './scene.css';

export interface View { lon: number; lat: number; distance: number; azimuth: number; elevation: number; instant?: boolean }

export function webglAvailable(): boolean {
  try {
    const c = document.createElement('canvas');
    return !!(c.getContext('webgl2') || c.getContext('webgl'));
  } catch {
    return false;
  }
}

export function useReducedMotion(): boolean {
  const [r, setR] = useState(() => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const m = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!m) return;
    const f = () => setR(m.matches);
    m.addEventListener('change', f);
    return () => m.removeEventListener('change', f);
  }, []);
  return r;
}

export function useTerrain(id: string | null) {
  const [t, setT] = useState<TerrainData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setT(null);
    if (!id) return;
    loadTerrain(id).then((d) => live && setT(d)).catch((e) => live && setErr(String(e)));
    return () => { live = false; };
  }, [id]);
  return { terrain: t, error: err };
}

function Rig({ frame, view, interactive, onAzimuth, smooth }: { frame: Frame; view: View | null; interactive: boolean; onAzimuth: (a: number, d: number) => void; smooth: number }) {
  const ref = useRef<CameraControls>(null);
  const { camera } = useThree();
  useEffect(() => {
    const c = ref.current;
    if (!c || !view) return;
    const [x, z] = frame.xz(view.lon, view.lat);
    const y = frame.yAt(x, z, 0);
    const az = THREE.MathUtils.degToRad(view.azimuth);
    const el = THREE.MathUtils.degToRad(view.elevation);
    const d = view.distance;
    // camera sits opposite to the azimuth it looks along (azimuth = compass direction the camera faces)
    const px = x - Math.sin(az) * Math.cos(el) * d;
    const pz = z + Math.cos(az) * Math.cos(el) * d;
    const py = y + Math.sin(el) * d;
    c.smoothTime = smooth;
    void c.setLookAt(px, py, pz, x, y, z, !view.instant);
  }, [frame, view, smooth]);
  useEffect(() => {
    (camera as THREE.PerspectiveCamera).far = frame.t.meta.extent_m * 6;
    camera.near = 5;
    camera.updateProjectionMatrix();
  }, [camera, frame]);
  return (
    <CameraControls
      ref={ref}
      enabled={interactive}
      minDistance={300}
      maxDistance={frame.t.meta.extent_m * 1.6}
      minPolarAngle={0.05}
      maxPolarAngle={Math.PI * 0.42}
      dollySpeed={0.4}
      truckSpeed={1}
      onChange={() => {
        const c = ref.current;
        if (!c) return;
        // compass azimuth the camera faces
        const dir = new THREE.Vector3();
        camera.getWorldDirection(dir);
        onAzimuth((THREE.MathUtils.radToDeg(Math.atan2(dir.x, -dir.z)) + 360) % 360, c.distance);
      }}
    />
  );
}

export function Scene3D({
  terrainId, view, interactive = true, children, summary, drapeOpacity = 0.2, height = '100%', smooth = 0.8, still,
}: {
  terrainId: string; view: View | null; interactive?: boolean; children?: (frame: Frame) => ReactNode; summary: string;
  drapeOpacity?: number; height?: string; smooth?: number; still?: ReactNode;
}) {
  const reduced = useReducedMotion();
  const gl = useMemo(webglAvailable, []);
  const { terrain } = useTerrain(terrainId);
  const frame = useMemo(() => (terrain ? new Frame(terrain) : null), [terrain]);
  const [az, setAz] = useState(0);
  const [dist, setDist] = useState(view?.distance ?? 5000);
  const [vh, setVh] = useState(600);
  const wrap = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setVh(el.clientHeight || 600));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const scale = scaleBar(dist, vh);
  return (
    <div ref={wrap} className="scene ticks" style={{ height }}>
      <p className="sr-only">{summary}</p>
      {!gl || (reduced && still) ? (
        still ?? (frame ? <StillView frame={frame} /> : null)
      ) : frame ? (
        <Canvas
          dpr={[1, 2]}
          camera={{ fov: 32, position: [0, frame.t.meta.extent_m * 0.6, frame.t.meta.extent_m * 0.6] }}
          gl={{ antialias: true, powerPreference: 'high-performance' }}
          onCreated={({ gl: r }) => r.setClearColor(COLORS.night)}
          aria-hidden
        >
          <Suspense fallback={null}>
            <TerrainMesh frame={frame} drapeOpacity={drapeOpacity} />
            {children?.(frame)}
            <Rig frame={frame} view={view} interactive={interactive && !reduced} onAzimuth={(a, d) => { setAz(a); setDist(d); }} smooth={reduced ? 0 : smooth} />
          </Suspense>
        </Canvas>
      ) : (
        <div className="scene-loading"><div className="skeleton" /></div>
      )}
      {!gl && <p className="scene-note tiny">3D unavailable; showing a plan view of the same data.</p>}
      {frame && (
        <div className="scene-hud mono" aria-hidden>
          <div className="north" style={{ transform: `rotate(${-az}deg)` }}>
            <svg width="22" height="22" viewBox="0 0 22 22"><line x1="11" y1="20" x2="11" y2="3" /><polyline points="7,8 11,3 15,8" /></svg>
            <span>N</span>
          </div>
          <div className="scalebar">
            <div className="scalebar-bar" style={{ width: scale.px }} />
            <span>{scale.label}</span>
          </div>
          <div className="ve">VE ×{frame.ve}</div>
        </div>
      )}
    </div>
  );
}

function scaleBar(distance: number, viewportH: number): { px: number; label: string } {
  const mpp = (2 * distance * Math.tan(THREE.MathUtils.degToRad(16))) / Math.max(viewportH, 1);
  const target = mpp * 90;
  const nice = [50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000];
  const m = nice.reduce((a, b) => (Math.abs(b - target) < Math.abs(a - target) ? b : a));
  return { px: Math.round(m / mpp), label: m >= 1000 ? `${m / 1000} km` : `${m} m` };
}
