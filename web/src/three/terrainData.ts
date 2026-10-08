import { useEffect, useState } from 'react';
import proj4 from 'proj4';
import { decode } from 'fast-png';

export interface TerrainMeta {
  crs: string; bounds_utm: [number, number, number, number]; bounds_wgs84: [number, number, number, number];
  centre_utm: [number, number]; px: number; res_m: number; site_id: string; kind: 'site' | 'city'; extent_m: number;
  min_m: number; max_m: number; vertical_exaggeration: number; contour_interval_m: number; dem: string;
  drape?: { scene: string; date: string; cloud_pct: number; res_m: number; credit: string } | null;
}

export interface TerrainData {
  id: string;
  meta: TerrainMeta;
  heights: Float32Array; // metres, row-major from north-west, px*px
  drapeUrl: string | null;
  epsg: number;
}

const projCache: Record<number, proj4.Converter> = {};
export function utm(epsg: number): proj4.Converter {
  if (!projCache[epsg]) {
    const zone = epsg % 100;
    const south = Math.floor(epsg / 100) === 327;
    projCache[epsg] = proj4('EPSG:4326', `+proj=utm +zone=${zone}${south ? ' +south' : ''} +datum=WGS84 +units=m +no_defs`);
  }
  return projCache[epsg];
}

const cache = new Map<string, Promise<TerrainData>>();

export function loadTerrain(id: string): Promise<TerrainData> {
  if (!cache.has(id)) {
    cache.set(id, (async () => {
      const meta = (await (await fetch(`/terrain/${id}/meta.json`)).json()) as TerrainMeta;
      const buf = await (await fetch(`/terrain/${id}/height.png`)).arrayBuffer();
      const png = decode(new Uint8Array(buf));
      const n = png.width * png.height;
      const raw = png.data as Uint16Array | Uint8Array;
      const maxv = png.depth === 16 ? 65535 : 255;
      const heights = new Float32Array(n);
      const ch = png.channels;
      for (let i = 0; i < n; i++) heights[i] = meta.min_m + (raw[i * ch] / maxv) * (meta.max_m - meta.min_m);
      return { id, meta, heights, drapeUrl: meta.drape ? `/terrain/${id}/drape.webp` : null, epsg: Number(meta.crs.split(':')[1]) };
    })());
  }
  return cache.get(id)!;
}

/** Scene frame: x = east (m) from tile centre, z = south (m) from tile centre, y = up (exaggerated m above min). */
export class Frame {
  readonly t: TerrainData;
  readonly cx: number; readonly cy: number; readonly ve: number; readonly half: number;
  constructor(t: TerrainData, ve?: number) {
    this.t = t;
    this.cx = t.meta.centre_utm[0];
    this.cy = t.meta.centre_utm[1];
    this.ve = ve ?? t.meta.vertical_exaggeration;
    this.half = t.meta.extent_m / 2;
  }
  xz(lon: number, lat: number): [number, number] {
    const [e, n] = utm(this.t.epsg).forward([lon, lat]);
    return [e - this.cx, -(n - this.cy)];
  }
  lonlat(x: number, z: number): [number, number] {
    const [lon, lat] = utm(this.t.epsg).inverse([x + this.cx, -z + this.cy]);
    return [lon, lat];
  }
  /** terrain height in metres (bilinear), null outside the tile */
  heightAt(x: number, z: number): number | null {
    const { px, extent_m } = this.t.meta;
    const u = (x + this.half) / extent_m * (px - 1);
    const v = (z + this.half) / extent_m * (px - 1);
    if (u < 0 || v < 0 || u > px - 1 || v > px - 1) return null;
    const i = Math.floor(u), j = Math.floor(v);
    const fu = u - i, fv = v - j;
    const H = this.t.heights;
    const i1 = Math.min(i + 1, px - 1), j1 = Math.min(j + 1, px - 1);
    const a = H[j * px + i], b = H[j * px + i1], c = H[j1 * px + i], d = H[j1 * px + i1];
    return (a * (1 - fu) + b * fu) * (1 - fv) + (c * (1 - fu) + d * fu) * fv;
  }
  y(h: number): number { return (h - this.t.meta.min_m) * this.ve; }
  yAt(x: number, z: number, lift = 0): number {
    const h = this.heightAt(x, z);
    return h === null ? lift : this.y(h) + lift;
  }
  inside(x: number, z: number, pad = 0): boolean { return Math.abs(x) <= this.half - pad && Math.abs(z) <= this.half - pad; }
}

export function polygonRings(g: GeoJSON.Polygon | GeoJSON.MultiPolygon): number[][][] {
  return g.type === 'Polygon' ? g.coordinates : g.coordinates.flat();
}

export function useTerrainData(id: string | null): TerrainData | null {
  const [t, setT] = useState<TerrainData | null>(null);
  useEffect(() => { if (id) loadTerrain(id).then(setT).catch(() => setT(null)); }, [id]);
  return t;
}
