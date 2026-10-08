import type { Lang } from '../i18n';

const MONTHS: Record<Lang, string[]> = {
  en: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
  hi: ['जन', 'फ़र', 'मार्च', 'अप्रै', 'मई', 'जून', 'जुला', 'अग', 'सितं', 'अक्टू', 'नवं', 'दिसं'],
};
export const MONTH_INITIALS: Record<Lang, string[]> = {
  en: ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'],
  hi: ['जन', 'फ़र', 'मा', 'अ', 'मई', 'जून', 'जु', 'अग', 'सि', 'अ', 'न', 'दि'],
};

export function dateLabel(iso: string, lang: Lang = 'en'): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${d} ${MONTHS[lang][m - 1]} ${y}`;
}

/** UTC 'YYYY-MM-DDTHH:MMZ' -> IST 'HH:MM' and date */
export function toIST(tsUtc: string): { date: string; time: string } {
  const t = Date.parse(tsUtc.replace('Z', ':00Z'));
  const ist = new Date(t + 330 * 60_000);
  const iso = ist.toISOString();
  return { date: iso.slice(0, 10), time: iso.slice(11, 16) };
}

export function km(m: number): string {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}

export function int(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  return n.toLocaleString('en-IN');
}

export function fixed(n: number | null | undefined, d = 1): string {
  if (n === null || n === undefined) return '—';
  return n.toFixed(d);
}

export const SAT: Record<string, string> = { N: 'Suomi NPP', N20: 'NOAA-20', '1': 'NOAA-20', N21: 'NOAA-21', '2': 'NOAA-21' };
export const CONF: Record<string, string> = { l: 'low', n: 'nominal', h: 'high' };

export function hourIST(tsIst: string): string {
  return tsIst.slice(11, 16);
}
