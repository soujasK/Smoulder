import { useState, type FormEvent } from 'react';
import { useT } from '../i18n';
import { liveEnabled, postSubscribe, useSnapshot } from '../data/snapshot';

/** Email subscription for downwind alerts. Location is rounded to 3 decimals before it leaves the browser. */
export function Subscribe({ lon, lat }: { lon: number; lat: number }) {
  const { t } = useT();
  const snap = useSnapshot();
  const [email, setEmail] = useState('');
  const [mode, setMode] = useState<'downwind' | 'all'>('downwind');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [msg, setMsg] = useState('');
  const r = (snap.data?.parameters.downwind as Record<string, number> | undefined)?.radius_km ?? 5;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!liveEnabled) return;
    setState('sending');
    try {
      const res = await postSubscribe({ email, lat: Math.round(lat * 1000) / 1000, lon: Math.round(lon * 1000) / 1000, mode });
      setState('sent');
      setMsg(res.message);
    } catch (err) {
      setState('error');
      setMsg(String(err));
    }
  }

  return (
    <section className="answer-sec subscribe" aria-labelledby="sub-h">
      <h2 id="sub-h" className="label">{t('sub.title')}</h2>
      <p className="small">{t('sub.body', { r })}</p>
      {!liveEnabled ? (
        <p className="note">{t('sub.offline')}</p>
      ) : state === 'sent' ? (
        <p className="note" role="status">{t('sub.sent')}{msg ? ` ${msg}` : ''}</p>
      ) : (
        <form onSubmit={submit} className="sub-form">
          <label className="field">
            <span className="label">{t('sub.email')}</span>
            <input className="input" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </label>
          <fieldset className="sub-mode">
            <legend className="sr-only">Mode</legend>
            <label><input type="radio" name="mode" checked={mode === 'downwind'} onChange={() => setMode('downwind')} /> {t('sub.mode.downwind')}</label>
            <label><input type="radio" name="mode" checked={mode === 'all'} onChange={() => setMode('all')} /> {t('sub.mode.all')}</label>
          </fieldset>
          <button className="btn" type="submit" disabled={state === 'sending'}>{t('sub.button')}</button>
          {state === 'error' && <p className="note" role="alert">{msg}</p>}
        </form>
      )}
    </section>
  );
}
