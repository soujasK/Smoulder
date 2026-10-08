import { useEffect, useMemo } from 'react';
import * as THREE from 'three';
import { useLoader } from '@react-three/fiber';
import type { Frame } from './terrainData';
import { COLORS } from './colors';

const vert = /* glsl */ `
  attribute float aHeight;
  varying float vH;
  varying vec2 vUv;
  varying vec3 vPos;
  void main() {
    vH = aHeight;
    vUv = uv;
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vPos = wp.xyz;
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

const frag = /* glsl */ `
  uniform vec3 uBase;
  uniform vec3 uEdge;
  uniform vec3 uMinor;
  uniform vec3 uMajor;
  uniform float uInterval;
  uniform float uMinorAlpha;
  uniform float uMajorAlpha;
  uniform sampler2D uDrape;
  uniform float uDrapeOpacity;
  uniform float uHasDrape;
  uniform vec3 uLightDir;
  uniform float uFade;
  varying float vH;
  varying vec2 vUv;
  varying vec3 vPos;

  float contour(float h, float interval) {
    float f = h / interval;
    float w = fwidth(f);
    float d = abs(fract(f - 0.5) - 0.5);
    return 1.0 - smoothstep(0.0, w * 1.2, d);
  }

  void main() {
    vec3 n = normalize(cross(dFdx(vPos), dFdy(vPos)));
    float diff = clamp(dot(n, normalize(uLightDir)), 0.0, 1.0);
    vec3 col = uBase * (0.86 + 0.18 * diff);
    if (uHasDrape > 0.5) {
      vec3 d = texture2D(uDrape, vUv).rgb;
      col = mix(col, mix(d, vec3(0.93), 0.18) * (0.88 + 0.2 * diff), uDrapeOpacity);
    }
    float minor = contour(vH, uInterval);
    float major = contour(vH, uInterval * 5.0);
    col = mix(col, uMinor, minor * uMinorAlpha);
    col = mix(col, uMajor, major * uMajorAlpha);
    // fade the tile edge into the scene background
    vec2 e = smoothstep(vec2(0.0), vec2(0.06), vUv) * smoothstep(vec2(0.0), vec2(0.06), 1.0 - vUv);
    float edge = e.x * e.y;
    gl_FragColor = vec4(mix(uEdge, col, edge * uFade + (1.0 - uFade)), 1.0);
    #include <colorspace_fragment>
  }
`;

export function TerrainMesh({ frame, drapeOpacity = 0.2, contourMinorAlpha, contourMajorAlpha, interval }: {
  frame: Frame; drapeOpacity?: number; contourMinorAlpha?: number; contourMajorAlpha?: number; interval?: number;
}) {
  const { t } = frame;
  const city = t.meta.kind === 'city';
  contourMinorAlpha ??= city ? 0.42 : 0.75;
  contourMajorAlpha ??= city ? 0.7 : 0.95;
  const px = t.meta.px;
  const geom = useMemo(() => {
    const g = new THREE.PlaneGeometry(t.meta.extent_m, t.meta.extent_m, px - 1, px - 1);
    g.rotateX(-Math.PI / 2); // plane in XZ, +z = south (row order matches north-west origin)
    const pos = g.attributes.position as THREE.BufferAttribute;
    const hAttr = new Float32Array(px * px);
    for (let i = 0; i < px * px; i++) {
      const h = t.heights[i];
      hAttr[i] = h;
      pos.setY(i, frame.y(h));
    }
    g.setAttribute('aHeight', new THREE.BufferAttribute(hAttr, 1));
    pos.needsUpdate = true;
    g.computeBoundingSphere();
    return g;
  }, [t, px, frame]);
  useEffect(() => () => geom.dispose(), [geom]);

  return t.drapeUrl ? (
    <DrapedMaterial geom={geom} frame={frame} url={t.drapeUrl} opacity={drapeOpacity} minor={contourMinorAlpha} major={contourMajorAlpha} interval={interval} />
  ) : (
    <PlainMaterial geom={geom} frame={frame} minor={contourMinorAlpha} major={contourMajorAlpha} interval={interval} />
  );
}

function useMaterial(frame: Frame, minor: number, major: number, interval: number | undefined, drape: THREE.Texture | null, opacity: number) {
  const mat = useMemo(() => new THREE.ShaderMaterial({
    vertexShader: vert,
    fragmentShader: frag,
    uniforms: {
      uBase: { value: new THREE.Color(COLORS.night2) },
      uEdge: { value: new THREE.Color(COLORS.night) },
      uMinor: { value: new THREE.Color(COLORS.ruleDarkLift) },
      uMajor: { value: new THREE.Color(COLORS.ash) },
      uInterval: { value: interval ?? frame.t.meta.contour_interval_m },
      uMinorAlpha: { value: minor },
      uMajorAlpha: { value: major },
      uDrape: { value: drape },
      uDrapeOpacity: { value: opacity },
      uHasDrape: { value: drape ? 1 : 0 },
      uLightDir: { value: new THREE.Vector3(-0.6, 0.45, -0.4) },
      uFade: { value: 1 },
    },
  }), [frame, minor, major, interval, drape, opacity]);
  useEffect(() => () => mat.dispose(), [mat]);
  return mat;
}

function DrapedMaterial({ geom, frame, url, opacity, minor, major, interval }: { geom: THREE.BufferGeometry; frame: Frame; url: string; opacity: number; minor: number; major: number; interval?: number }) {
  const tex = useLoader(THREE.TextureLoader, url);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  const mat = useMaterial(frame, minor, major, interval, tex, opacity);
  return <mesh geometry={geom} material={mat} />;
}

function PlainMaterial({ geom, frame, minor, major, interval }: { geom: THREE.BufferGeometry; frame: Frame; minor: number; major: number; interval?: number }) {
  const mat = useMaterial(frame, minor, major, interval, null, 0);
  return <mesh geometry={geom} material={mat} />;
}
