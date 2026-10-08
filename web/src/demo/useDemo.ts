import { useEffect, useMemo, useState } from 'react';
import { useSnapshot } from '../data/snapshot';
import { useLang } from '../i18n';
import { buildScript, DEMO_CITY, DEMO_SITE, DEMO_YEAR, QUESTION_EN, QUESTION_HI, YEAR_MS, type Step } from './script';
import type { View } from '../three/Scene3D';

export interface DemoState {
  active: boolean; step: number; question?: string; typed?: string; submit?: string; year?: string; city?: string; view?: View | null; yearMs: number;
}

export function useDemo(enabled: boolean): DemoState {
  const snap = useSnapshot();
  const lang = useLang((s) => s.lang);
  const [i, setI] = useState(-1);

  const plan = useMemo(() => {
    const d = snap.data;
    if (!enabled || !d) return null;
    const site = d.siteById[DEMO_SITE];
    const lms = d.landmarks.filter((l) => l.id.startsWith(`${DEMO_SITE}-`) && l.results[DEMO_YEAR]);
    if (!site || lms.length === 0) return null;
    lms.sort((a, b) => (b.results[DEMO_YEAR].smoke_days - a.results[DEMO_YEAR].smoke_days) || a.name.localeCompare(b.name));
    const lm = lms[0];
    const cs = d.sites.filter((s) => s.city === DEMO_CITY);
    const centre: [number, number] = [cs.reduce((a, s) => a + s.centroid[0], 0) / cs.length, cs.reduce((a, s) => a + s.centroid[1], 0) / cs.length];
    return { landmark: lm.name, steps: buildScript(lm.name, lang === 'hi' ? QUESTION_HI : QUESTION_EN, centre) };
  }, [enabled, snap.data, lang]);

  useEffect(() => {
    if (!plan) return;
    document.body.classList.add('demo-mode');
    const timers = plan.steps.map((s, k) => window.setTimeout(() => setI(k), s.at));
    return () => { timers.forEach(clearTimeout); document.body.classList.remove('demo-mode'); };
  }, [plan]);

  if (!plan || i < 0) return { active: !!plan, step: i, yearMs: YEAR_MS, question: plan ? '' : undefined, year: plan ? DEMO_YEAR : undefined, city: plan ? DEMO_CITY : undefined };
  // fold steps up to i
  const acc: Step = { at: 0 };
  let lastView: Step['view'] | undefined;
  for (let k = 0; k <= i; k++) {
    const s = plan.steps[k];
    if (s.question !== undefined) acc.question = s.question;
    if (s.typed !== undefined) acc.typed = s.typed;
    if (s.view !== undefined) lastView = s.view;
  }
  const cur = plan.steps[i];
  return {
    active: true,
    step: i,
    question: acc.question,
    typed: acc.typed,
    submit: cur.submit ? plan.landmark : undefined,
    year: DEMO_YEAR,
    city: DEMO_CITY,
    view: lastView ?? null,
    yearMs: YEAR_MS,
  };
}
