import { Link, NavLink } from 'react-router-dom';
import { useLang, useT } from '../i18n';
import { useLive, useSnapshot, liveEnabled } from '../data/snapshot';
import { dateLabel, SAT, toIST } from '../lib/format';
import './chrome.css';

export function Masthead({ hidden = false }: { hidden?: boolean }) {
  const { t, lang } = useT();
  const setLang = useLang((s) => s.setLang);
  if (hidden) return null;
  return (
    <header className="masthead page">
      <a className="sr-only skip" href="#main">{t('nav.skip')}</a>
      <Link to="/" className="wordmark" aria-label="Smoulder, home">SMOULDER</Link>
      <nav className="nav" aria-label="Main">
        <div className="lang" role="group" aria-label="Language">
          <button aria-pressed={lang === 'en'} onClick={() => setLang('en')} className={lang === 'en' ? 'on' : ''}>EN</button>
          <span aria-hidden className="muted">|</span>
          <button aria-pressed={lang === 'hi'} onClick={() => setLang('hi')} className={lang === 'hi' ? 'on' : ''} lang="hi">हिं</button>
        </div>
        <NavLink to="/sites">{t('nav.sites')}</NavLink>
        <NavLink to="/method">{t('nav.method')}</NavLink>
        <NavLink to="/pipeline">{t('nav.pipeline')}</NavLink>
      </nav>
    </header>
  );
}

/** "Last detection: Ghazipur, 01:42 IST, VIIRS NOAA-21, Tier A" — live feed or latest in snapshot. */
export function LiveStrip() {
  const { t } = useT();
  const snap = useSnapshot();
  const live = useLive();
  const d = snap.data;
  if (!d) return null;
  let det = live.data?.last_detection ?? null;
  let isLive = !!live.data;
  if (!det) {
    const counted = d.detections.filter((x) => x.counted);
    const last = counted.reduce<typeof counted[number] | null>((a, b) => (!a || b.ts_utc > a.ts_utc ? b : a), null);
    det = last ? { ...last, site_name: d.siteById[last.site_id]?.name ?? last.site_id } : null;
    isLive = false;
  }
  return (
    <div className="livestrip page mono" role="status">
      <span className="label">{t('live.last')}</span>
      {det ? (
        <Link to={`/site/${det.site_id}`}>
          {det.site_name}, {dateLabel(toIST(det.ts_utc).date)} {toIST(det.ts_utc).time} IST, VIIRS {SAT[det.satellite] ?? det.satellite}, Tier {det.tier}
        </Link>
      ) : <span>{t('live.none')}</span>}
      <span className="muted tiny">{isLive ? 'live' : `${t('footer.through')} ${dateLabel(d.data_through)}`}</span>
    </div>
  );
}

export function StatusBanner() {
  const { t } = useT();
  const snap = useSnapshot();
  const d = snap.data;
  if (!d) return null;
  if (d.liveError) return <div className="banner page" role="alert">{t('state.error', { date: dateLabel(d.data_through) })}</div>;
  if (d.sample) return <div className="banner page" role="alert">{t('state.sample')}</div>;
  if (!liveEnabled) return <div className="banner banner-quiet page">{t('state.offline', { date: dateLabel(d.data_through) })}</div>;
  return null;
}

export function Footer() {
  const { t } = useT();
  const snap = useSnapshot();
  return (
    <footer className="footer page">
      <hr className="rule" />
      <div className="footer-row">
        <p className="tiny muted">{t('footer.credits')}</p>
        {snap.data && (
          <p className="tiny muted mono">
            {t('footer.run')} {snap.data.pipeline_run_id} · {t('footer.through')} {snap.data.data_through}
          </p>
        )}
      </div>
    </footer>
  );
}

export function Loading() {
  const { t } = useT();
  return (
    <div className="page" aria-busy="true" aria-live="polite" style={{ paddingTop: 48 }}>
      <span className="sr-only">{t('state.loading')}</span>
      <div className="skeleton" /><div className="skeleton" style={{ width: '60%' }} /><div className="skeleton" style={{ width: '80%' }} />
    </div>
  );
}
