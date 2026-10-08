// Demo Mode (?demo=1): fixed timings and camera keyframes for the screen recording.
// Deterministic: the landmark is chosen by a fixed rule from the committed snapshot
// (public station near DEMO_SITE with the most smoke days in DEMO_YEAR; ties by name).

export const DEMO_SITE = 'bhalswa';
export const DEMO_YEAR = 'all';
export const DEMO_CITY = 'delhi';

export interface Step {
  at: number; // ms from start
  question?: string; // typed question so far
  typed?: string; // input text so far
  submit?: boolean;
  view?: { lon: number; lat: number; distance: number; azimuth: number; elevation: number } | null;
}

export const QUESTION_EN = 'How many days was your area downwind of a burning landfill?';
export const QUESTION_HI = 'आपका इलाक़ा कितने दिन जलते कूड़े के पहाड़ की हवा की दिशा में रहा?';

/** Builds the step list once the landmark is known. Total runtime ~22 s (moments 1 and 2). */
export function buildScript(landmark: string, question: string, centre: [number, number]): Step[] {
  const steps: Step[] = [];
  // 0-1.2 s: night, contour lines of the city, wide view from the south
  steps.push({ at: 0, question: '', typed: '', view: { lon: centre[0], lat: centre[1] - 0.02, distance: 44000, azimuth: 12, elevation: 58 } });
  // 1.2-4.2 s: the question types in
  const qStart = 1200, qDur = 3000;
  for (let i = 1; i <= question.length; i++) steps.push({ at: qStart + (qDur * i) / question.length, question: question.slice(0, i) });
  // 4.6-6.6 s: the landmark is typed into the input; camera eases closer
  steps.push({ at: 4400, view: { lon: centre[0], lat: centre[1], distance: 26000, azimuth: 18, elevation: 46 } });
  const tStart = 4800, tDur = 1600;
  for (let i = 1; i <= landmark.length; i++) steps.push({ at: tStart + (tDur * i) / landmark.length, typed: landmark.slice(0, i) });
  // 7.0 s: submit; the Home screen's answer view takes the camera down toward the site
  steps.push({ at: 7000, submit: true, view: null });
  return steps;
}

/** The year plays over this many ms after submit (moment 2). */
export const YEAR_MS = 11000;
