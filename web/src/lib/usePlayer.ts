import { useEffect, useRef, useState } from 'react';

/** Plays a value from 0 to 1 over `ms`; returns progress. Instant when disabled. */
export function usePlayer(key: string | null, ms: number, enabled: boolean, delay = 0): { p: number; playing: boolean; skip: () => void } {
  const [p, setP] = useState(enabled ? 0 : 1);
  const raf = useRef(0);
  const skipRef = useRef(false);
  useEffect(() => {
    skipRef.current = false;
    if (!key) { setP(0); return; }
    if (!enabled) { setP(1); return; }
    setP(0);
    const t0 = performance.now() + delay;
    const tick = (t: number) => {
      if (skipRef.current) { setP(1); return; }
      const v = Math.max(0, Math.min(1, (t - t0) / ms));
      setP(v);
      if (v < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [key, ms, enabled, delay]);
  return { p, playing: p > 0 && p < 1, skip: () => { skipRef.current = true; setP(1); } };
}

export function dayOfYear(iso: string): number {
  const y = Number(iso.slice(0, 4));
  return (Date.UTC(y, Number(iso.slice(5, 7)) - 1, Number(iso.slice(8, 10))) - Date.UTC(y, 0, 1)) / 86400000;
}

export function isoFromDay(year: number, day: number): string {
  return new Date(Date.UTC(year, 0, 1) + Math.floor(day) * 86400000).toISOString().slice(0, 10);
}

export function daysInYear(y: number): number {
  return (Date.UTC(y + 1, 0, 1) - Date.UTC(y, 0, 1)) / 86400000;
}
