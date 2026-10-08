import { create } from 'zustand';
import en from './en.json';
import hi from './hi.json';

export type Lang = 'en' | 'hi';
const DICTS: Record<Lang, Record<string, string>> = { en, hi };

function initialLang(): Lang {
  try {
    const q = new URLSearchParams(window.location.search).get('lang');
    if (q === 'hi' || q === 'en') return q;
    const s = window.localStorage.getItem('smoulder.lang');
    if (s === 'hi' || s === 'en') return s;
  } catch { /* storage unavailable */ }
  return 'en';
}

interface LangState { lang: Lang; setLang: (l: Lang) => void }
export const useLang = create<LangState>((set) => ({
  lang: initialLang(),
  setLang: (lang) => {
    try { window.localStorage.setItem('smoulder.lang', lang); } catch { /* ignore */ }
    document.documentElement.lang = lang;
    set({ lang });
  },
}));

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  let s = DICTS[lang][key] ?? DICTS.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  return s;
}

export function useT() {
  const lang = useLang((s) => s.lang);
  return { lang, t: (key: string, vars?: Record<string, string | number>) => translate(lang, key, vars) };
}

export const ALL_KEYS = Object.keys(en);
