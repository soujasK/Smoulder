import { useQuery } from '@tanstack/react-query';
import { API_BASE_URL, DATA_MODE, SNAPSHOT_URL } from '../config';
import type { Detection, Episode, FireDay, Site, Snapshot, SmokeDaysResponse, Run } from '../types/contract';

export interface Indexed extends Snapshot {
  siteById: Record<string, Site>;
  detBySite: Record<string, Detection[]>;
  fdBySite: Record<string, FireDay[]>;
  epBySite: Record<string, Episode[]>;
  liveError: string | null;
}

function index(s: Snapshot, liveError: string | null): Indexed {
  const siteById: Record<string, Site> = {};
  const detBySite: Record<string, Detection[]> = {};
  const fdBySite: Record<string, FireDay[]> = {};
  const epBySite: Record<string, Episode[]> = {};
  for (const x of s.sites) { siteById[x.site_id] = x; detBySite[x.site_id] = []; fdBySite[x.site_id] = []; epBySite[x.site_id] = []; }
  for (const d of s.detections) detBySite[d.site_id]?.push(d);
  for (const f of s.fire_days) fdBySite[f.site_id]?.push(f);
  for (const e of s.episodes) epBySite[e.site_id]?.push(e);
  return { ...s, siteById, detBySite, fdBySite, epBySite, liveError };
}

async function getJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json() as Promise<T>;
}

/** Live mode: the API serves the latest published snapshot; on failure fall back to the committed one. */
async function loadSnapshot(): Promise<Indexed> {
  if (DATA_MODE === 'live' && API_BASE_URL) {
    try {
      const live = await getJSON<Snapshot>(`${API_BASE_URL}/snapshot`);
      return index(live, null);
    } catch (e) {
      const local = await getJSON<Snapshot>(SNAPSHOT_URL);
      return index(local, String(e));
    }
  }
  return index(await getJSON<Snapshot>(SNAPSHOT_URL), null);
}

export function useSnapshot() {
  return useQuery({ queryKey: ['snapshot'], queryFn: loadSnapshot, staleTime: Infinity, retry: 1 });
}

export interface LiveFeed { last_detection: (Detection & { site_name: string }) | null; checked_at: string; run_id: string | null }

export function useLive() {
  return useQuery({
    queryKey: ['live'],
    enabled: DATA_MODE === 'live' && !!API_BASE_URL,
    queryFn: () => getJSON<LiveFeed>(`${API_BASE_URL}/live`),
    refetchInterval: 60_000,
  });
}

export function useRuns() {
  return useQuery({
    queryKey: ['runs'],
    enabled: DATA_MODE === 'live' && !!API_BASE_URL,
    queryFn: () => getJSON<{ runs: Run[]; time_to_alert: { det_id: string; site_id: string; acq_ts: string; first_seen_ts: string; alert_sent_ts: string; replay: boolean }[] }>(`${API_BASE_URL}/runs/latest`),
    refetchInterval: 60_000,
  });
}

export async function fetchSmokeDays(q: string, year: string): Promise<SmokeDaysResponse> {
  return getJSON<SmokeDaysResponse>(`${API_BASE_URL}/smoke-days?q=${encodeURIComponent(q)}&year=${encodeURIComponent(year)}`);
}

export async function postSubscribe(body: { email: string; lat: number; lon: number; mode: 'downwind' | 'all' }): Promise<{ status: string; message: string }> {
  return getJSON(`${API_BASE_URL}/subscribe`, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
}

export const liveEnabled = DATA_MODE === 'live' && !!API_BASE_URL;
