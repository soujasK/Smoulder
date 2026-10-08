// Screenshot pages for visual QA: node scripts/shoot.mjs <outdir> <path>[@WxH][#waitms] ...
import { chromium } from '../web/node_modules/playwright/index.mjs';

const [outDir, ...targets] = process.argv.slice(2);
const base = process.env.BASE ?? 'http://localhost:5179';
const browser = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
for (const t of targets) {
  const m = t.match(/^([^@#]+)(?:@(\d+)x(\d+))?(?:#(\d+))?$/);
  const [, path, w = '1440', h = '900', wait = '4000'] = m;
  const page = await browser.newPage({ viewport: { width: Number(w), height: Number(h) }, deviceScaleFactor: 1 });
  const errs = [];
  page.on('console', (msg) => { if (msg.type() === 'error') errs.push(msg.text()); });
  page.on('pageerror', (e) => errs.push(String(e)));
  await page.goto(base + path, { waitUntil: 'networkidle' }).catch((e) => errs.push(String(e)));
  await page.waitForTimeout(Number(wait));
  const name = path.replace(/[^a-z0-9]+/gi, '_') + `_${w}.png`;
  await page.screenshot({ timeout: 120000, path: `${outDir}/${name}`, fullPage: process.env.FULL === '1' });
  const sw = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  console.log(name, 'hscroll', sw, errs.length ? 'ERRORS: ' + errs.slice(0, 5).join(' | ') : 'ok');
  await page.close();
}
await browser.close();
