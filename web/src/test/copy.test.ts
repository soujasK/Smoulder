import { resolve } from 'node:path';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import en from '../i18n/en.json';
import hi from '../i18n/hi.json';

const BANNED = ['illegal', 'negligent', 'cover-up', 'deliberate', 'saved', 'prevented', 'avoided', 'toxic', 'poisoned', 'exposed'];
const re = new RegExp(`\b(${BANNED.join('|')})\b`, 'i');

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((f) => { const p = join(dir, f); return statSync(p).isDirectory() ? files(p) : p.endsWith('.tsx') ? [p] : []; });
}

describe('copy lint', () => {
  it('UI dictionaries contain no banned words', () => {
    for (const [k, v] of Object.entries({ ...en, ...hi })) expect(re.test(v), `${k}: ${v}`).toBe(false);
  });
  it('briefs in the snapshot contain no banned words', () => {
    const snap = JSON.parse(readFileSync(resolve(process.cwd(), 'public/data/snapshot.json'), 'utf-8')) as { briefs: { text: string }[] };
    for (const b of snap.briefs) expect(re.test(b.text), b.text).toBe(false);
  });
  it('JSX copy contains no banned words', () => {
    for (const f of files(resolve(process.cwd(), 'src'))) {
      const text = readFileSync(f, 'utf-8').replace(/\/\/.*$/gm, '');
      const m = text.match(re);
      expect(m?.[0], f).toBeUndefined();
    }
  });
  it('Hindi dictionary covers every English key', () => {
    expect(Object.keys(hi).sort()).toEqual(Object.keys(en).sort());
  });
});
