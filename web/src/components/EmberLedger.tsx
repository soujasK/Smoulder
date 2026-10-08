import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useT } from '../i18n';
import type { Indexed } from '../data/snapshot';
import type { FireDay } from '../types/contract';
import { dateLabel, fixed, SAT, toIST } from '../lib/format';
import { Metric } from './Tier';
import './ledger.css';

/** Every counted fire day at every site, on one time axis. News-reported days carry a ring. */
export function EmberLedger({ d }: { d: Indexed }) {
  const { t, lang } = useT();
  const nav = useNavigate();
  const box = useRef<HTMLDivElement>(null);
  const [lit, setLit] = useState(false);
  const [tip, setTip] = useState<{ fd: FireDay; x: number; row: number } | null>(null);

  const start = Date.parse(d.sites[0]?.stats.first_data_date ?? '2019-01-01');
  const end = Date.parse(d.data_through);
  const span = end - start;
  const pos = (iso: string) => (Date.parse(iso) - start) / span;
  const firstYear = new Date(start).getUTCFullYear();
  const lastYear = new Date(end).getUTCFullYear();
  const years = useMemo(() => Array.from({ length: lastYear - firstYear + 1 }, (_, i) => firstYear + i), [firstYear, lastYear]);

  const reported = useMemo(() => {
    const s = new Set<string>();
    for (const e of d.validation.events) for (const x of e.detection_dates) s.add(`${e.site_id}:${x}`);
    return s;
  }, [d]);

  const rows = useMemo(() => [...d.sites].sort((a, b) => (d.fdBySite[b.site_id]?.length ?? 0) - (d.fdBySite[a.site_id]?.length ?? 0)), [d]);
  const maxDet = Math.max(1, ...d.fire_days.map((f) => f.detections));

  useEffect(() => {
    const el = box.current;
    if (!el || typeof IntersectionObserver === 'undefined') { setLit(true); return; }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { setLit(true); io.disconnect(); } }, { threshold: 0.25 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const fireDays = d.fire_days.length;
  const unreported = d.validation.fire_days_without_news;
  const people1 = d.sites.reduce((a, s) => a + (s.context?.people_1km_est ?? 0), 0);
  const lakh = people1 / 100000;
  const firms = d.sources.find((s) => s.id.toLowerCase().includes('firms'));
  const worldpop = d.sources.find((s) => s.id.toLowerCase().includes('worldpop'));

  return (
    <section className="ledger-sec page" aria-labelledby="record-h">
      <div className="ledger-head">
        <p className="label ledger-kicker"><span className="ember-dot" aria-hidden />{t('record.kicker', { n: d.sites.length, from: firstYear, to: lastYear })}</p>
        <h2 id="record-h" className="serif ledger-title">{t('record.title')}</h2>
      </div>

      <div className="ledger-stats">
        <Metric big value={fireDays} unit={t('record.stat.days')} tier="MEASURED"
          receipt={{ source: firms?.name ?? 'NASA FIRMS VIIRS 375 m', href: firms?.url, method: t('record.stat.days.method'), date: `${dateLabel(d.sites[0].stats.first_data_date, lang)} – ${dateLabel(d.data_through, lang)}` }} />
        <Metric big value={unreported} unit={t('record.stat.unreported', { n: fireDays })} tier="COMPILED"
          receipt={{ source: d.sources.find((s) => s.id === 'news')?.name ?? t('record.stat.unreported.source'), method: d.validation.note || t('record.stat.unreported.method'), date: dateLabel(d.data_through, lang) }} />
        <Metric big value={`~${fixed(lakh, 1)}`} unit={t('record.stat.people')} tier="ESTIMATED"
          receipt={{ source: worldpop?.name ?? 'WorldPop 2020', href: worldpop?.url, method: t('record.stat.people.method'), date: d.sites[0].context?.retrieved_on ?? d.data_through }} />
      </div>

      <div ref={box} className={`ledger-board${lit ? ' is-lit' : ''}`} role="img"
        aria-label={t('record.aria', { n: fireDays, sites: d.sites.length, from: firstYear, to: dateLabel(d.data_through, lang) })}>
        <div className="ledger-axis" aria-hidden>
          <span />
          <div className="ledger-years">
            {years.map((y) => {
              const x = pos(`${y}-01-01`);
              return x < 1 ? <span key={y} className="mono" style={{ left: `${Math.max(0, x) * 100}%` }}>{y}</span> : null;
            })}
          </div>
        </div>
        {rows.map((s, ri) => {
          const fds = d.fdBySite[s.site_id] ?? [];
          return (
            <div key={s.site_id} className="ledger-row">
              <Link to={`/site/${s.site_id}`} className="ledger-site">
                <span className="ledger-name">{s.name}</span>
                <span className="ledger-city">{s.city_name}</span>
                <span className="num ledger-n">{fds.length}</span>
              </Link>
              <div className="ledger-track">
                {years.map((y) => { const x = pos(`${y}-01-01`); return x > 0 && x < 1 ? <span key={y} className="ledger-grid" style={{ left: `${x * 100}%` }} /> : null; })}
                {fds.length === 0 && <span className="ledger-none mono">{t('record.none')}</span>}
                {fds.map((f) => {
                  const x = pos(f.date_ist);
                  const h = 30 + 70 * Math.log1p(f.detections) / Math.log1p(maxDet);
                  const hot = Math.min(1, (f.max_frp_mw ?? 1) / 12);
                  const news = reported.has(`${s.site_id}:${f.date_ist}`);
                  return (
                    <button key={f.date_ist} type="button" className={`ember${news ? ' ember-news' : ''}`}
                      style={{ left: `${x * 100}%`, height: `${h}%`, ['--hot' as string]: hot, animationDelay: `${(x * 1.8).toFixed(2)}s` }}
                      aria-label={`${s.name}, ${dateLabel(f.date_ist, lang)}, ${f.detections} detections${news ? ', reported in the news' : ''}`}
                      onMouseEnter={() => setTip({ fd: f, x, row: ri })} onMouseLeave={() => setTip(null)}
                      onFocus={() => setTip({ fd: f, x, row: ri })} onBlur={() => setTip(null)}
                      onClick={() => nav(`/site/${s.site_id}`)} />
                  );
                })}
                {tip && tip.row === ri && (
                  <div className={`ledger-tip${tip.x > 0.7 ? ' is-left' : ''}`} style={{ left: `${tip.x * 100}%` }} role="status">
                    <strong className="mono">{dateLabel(tip.fd.date_ist, lang)}</strong>
                    <span>{s.name} · {tip.fd.detections} {t('record.tip.det')} · {tip.fd.max_frp_mw !== null ? `${fixed(tip.fd.max_frp_mw, 1)} MW` : '—'}</span>
                    <span className="muted">{t('record.tip.first')} {toIST(tip.fd.first_ts_utc).time} IST · {tip.fd.satellites.map((x) => SAT[x] ?? x).join(', ')}</span>
                    <span className={reported.has(`${s.site_id}:${tip.fd.date_ist}`) ? 'tip-news' : 'tip-quiet'}>
                      {reported.has(`${s.site_id}:${tip.fd.date_ist}`) ? t('record.tip.news') : t('record.tip.nonews')}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
        <div className="ledger-legend tiny muted">
          <span><i className="lg-ember" />{t('record.legend.day')}</span>
          <span><i className="lg-news" />{t('record.legend.news')}</span>
          <span>{t('record.legend.height')}</span>
        </div>
      </div>
    </section>
  );
}
