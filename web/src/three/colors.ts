// Mirrors styles/tokens.css for WebGL (CSS variables are not readable by shaders).
export const COLORS = {
  // light "morning haze" scene: night* keep their names but now mean the scene background and terrain base
  night: '#EEF0ED', night2: '#E6E8E2', night3: '#DCDFD8', ruleDark: '#CDD2CD', ruleDarkLift: '#A7B2B3',
  ash: '#6F7E86', bone: '#1F2B33',
  ember1: '#F7E6DA', ember2: '#E9A47C', ember3: '#E07B45', ember4: '#D2652F', ember5: '#B04A1E',
  wind: '#4C7C95',
};

export const EMBER_RAMP = [COLORS.ember2, COLORS.ember3, COLORS.ember4, COLORS.ember5];

/** FRP (MW) -> ember colour and a 0..1 scale (log). */
export function frpScale(frp: number | null): number {
  const f = Math.max(0.1, frp ?? 1);
  return Math.min(1, Math.log10(1 + f) / Math.log10(1 + 60));
}
export function frpColor(frp: number | null): string {
  const s = frpScale(frp);
  const i = Math.min(EMBER_RAMP.length - 1, Math.floor(s * EMBER_RAMP.length));
  return EMBER_RAMP[i];
}
