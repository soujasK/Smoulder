import { useRuns, useSnapshot, liveEnabled } from '../data/snapshot';
import type { Run } from '../types/contract';
import { TierChip } from '../components/Tier';
import './pipeline.css';

function dur(a: string, b: string): string {
  const s = Math.max(0, (Date.parse(b) - Date.parse(a)) / 1000);
  return s < 90 ? `${s.toFixed(0)} s` : `${(s / 60).toFixed(1)} min`;
}

function fmtTs(ts: string): string {
  const t = new Date(Date.parse(ts) + 330 * 60000).toISOString();
  return `${t.slice(0, 10)} ${t.slice(11, 19)} IST`;
}

export function Pipeline() {
  const snap = useSnapshot();
  const live = useRuns();
  const d = snap.data;
  if (!d) return null;
  const runs: Run[] = live.data?.runs?.length ? live.data.runs : d.runs;
  const tta = live.data?.time_to_alert ?? [];
  return (
    <main id="main" className="pipeline page">
      <header className="method-head">
        <p className="label">Pipeline · {liveEnabled ? (live.data ? 'live from the API' : live.isError ? 'API unavailable: showing the snapshot run' : 'loading') : 'offline snapshot'}</p>
        <h1 className="serif">Where the numbers are made</h1>
        <p className="lede serif">Two AWS Step Functions state machines: <b>Backfill</b> rebuilds the record from open data; <b>Watch</b> runs every 30 minutes and sends downwind alerts.</p>
      </header>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">01</span><h2>Architecture</h2></div>
        <Architecture />
        <p className="fig-cap"><span className="fig-no">Fig. 1.</span>Region ap-south-1. Open data enters from the left (NASA FIRMS, Open-Meteo, Sentinel-2 and Copernicus DEM on the AWS Open Data registry, OpenStreetMap, WorldPop); the public reads from Amplify and the HTTP API; alerts leave by SNS email.</p>
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">02</span><h2>Last runs</h2></div>
        {runs.length === 0 && <p className="small muted">No runs recorded.</p>}
        {runs.map((r) => (
          <article key={r.run_id} className="run">
            <header className="run-head mono">
              <span className={`run-kind run-${r.kind}`}>{r.kind.toUpperCase()}</span>
              <span>{r.run_id}</span>
              <span className="muted">{fmtTs(r.started_at)}</span>
              <span>{dur(r.started_at, r.ended_at)}</span>
              <span className={r.status === 'SUCCEEDED' ? 'ok' : 'bad'}>{r.status}</span>
              <span className="muted">{r.where}</span>
            </header>
            <ol className="stages">
              {r.stages.map((s) => (
                <li key={s.name + s.started_at}>
                  <span className="stage-name">{s.name}</span>
                  <span className="mono tiny">{dur(s.started_at, s.ended_at)}</span>
                  <span className="mono tiny muted">{s.count ?? ''}</span>
                  <span className={`mono tiny ${s.status === 'SUCCEEDED' ? 'ok' : 'bad'}`}>{s.status}</span>
                </li>
              ))}
            </ol>
          </article>
        ))}
      </section>

      <section className="sec">
        <div className="sec-head"><span className="sec-no">03</span><h2>Time to alert</h2><TierChip tier="MEASURED" /></div>
        {tta.length === 0 ? <p className="small muted">{liveEnabled ? 'No alerts sent yet.' : 'Alert logs are read from the live API; this is the offline snapshot.'}</p> : (
          <div className="ledger-wrap">
            <table className="ledger">
              <thead><tr><th>Detection</th><th>Site</th><th>Acquired</th><th>First seen</th><th>Alert sent</th><th className="r">Acq. → alert</th><th className="r">Seen → alert</th></tr></thead>
              <tbody>{tta.map((x) => (
                <tr key={x.det_id + x.alert_sent_ts}><td className="mono tiny">{x.det_id}{x.replay ? ' REPLAY' : ''}</td><td>{d.siteById[x.site_id]?.name}</td><td className="mono tiny">{fmtTs(x.acq_ts)}</td><td className="mono tiny">{fmtTs(x.first_seen_ts)}</td><td className="mono tiny">{fmtTs(x.alert_sent_ts)}</td><td className="num r">{x.replay ? '—' : dur(x.acq_ts, x.alert_sent_ts)}</td><td className="num r">{dur(x.first_seen_ts, x.alert_sent_ts)}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        <p className="tiny muted">Acquisition → alert includes the FIRMS publication delay for NRT data (typically 1–3 h after the overpass). Seen → alert is our own latency. Replays have no meaningful acquisition latency.</p>
      </section>
    </main>
  );
}

/** Thin-line architecture diagram in the design tokens (no vendor icons). */
function Architecture() {
  const B = ({ x, y, w = 132, h = 34, t, s }: { x: number; y: number; w?: number; h?: number; t: string; s?: string }) => (
    <g>
      <rect x={x} y={y} width={w} height={h} className="arch-box" />
      <text x={x + 8} y={y + 15} className="arch-t">{t}</text>
      {s && <text x={x + 8} y={y + 27} className="arch-s">{s}</text>}
    </g>
  );
  const L = ({ d, wind = false }: { d: string; wind?: boolean }) => <path d={d} className={wind ? 'arch-l arch-w' : 'arch-l'} markerEnd="url(#arr)" />;
  return (
    <div className="arch-wrap">
      <svg viewBox="0 0 960 400" className="arch" role="img" aria-label="Architecture: open data sources feed Step Functions Backfill and Watch, which run Lambda tasks writing to S3 and DynamoDB; API Gateway and Amplify serve the web app; SNS sends email alerts; Bedrock writes briefs; Amazon Location geocodes addresses.">
        <defs><marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8" fill="none" stroke="#7E8C93" /></marker></defs>
        <text x={0} y={14} className="arch-h">OPEN DATA</text>
        <B x={0} y={28} t="NASA FIRMS" s="VIIRS SP + NRT" />
        <B x={0} y={72} t="Open-Meteo" s="hourly 10 m wind" />
        <B x={0} y={116} t="Sentinel-2 L2A" s="AWS Open Data · STAC" />
        <B x={0} y={160} t="Copernicus DEM" s="AWS Open Data" />
        <B x={0} y={204} t="OpenStreetMap" s="Overpass" />
        <B x={0} y={248} t="WorldPop" s="2020, 100 m" />

        <text x={200} y={14} className="arch-h">AWS · ap-south-1</text>
        <B x={200} y={28} w={150} t="EventBridge Scheduler" s="every 30 min" />
        <B x={200} y={100} w={150} h={64} t="Step Functions" s="Backfill · Watch" />
        <B x={200} y={200} w={150} t="SSM Parameter Store" s="FIRMS key" />
        <B x={400} y={64} w={150} h={136} t="Lambda" s="fetch · attribute · wind" />
        <text x={408} y={124} className="arch-s">downwind · burn scan</text>
        <text x={408} y={136} className="arch-s">terrain · context · publish</text>
        <B x={600} y={28} w={150} t="S3" s="raw · imagery · public" />
        <B x={600} y={84} w={150} t="DynamoDB" s="record · alerts · runs" />
        <B x={600} y={140} w={150} t="Amazon Bedrock" s="briefs, number-checked" />
        <B x={600} y={196} w={150} t="Amazon SNS" s="email alerts" />
        <B x={600} y={270} w={150} t="API Gateway + Lambda" s="HTTP API" />
        <B x={400} y={270} w={150} t="Amazon Location" s="Places geocoding" />
        <B x={600} y={340} w={150} t="Amplify Hosting" s="web app" />
        <B x={400} y={340} w={150} t="CloudWatch" s="dashboard · alarms" />

        <text x={810} y={14} className="arch-h">PEOPLE</text>
        <B x={810} y={196} w={140} t="Subscribers" s="email" />
        <B x={810} y={300} w={140} t="Residents, press," s="officials, judges" />

        <L d="M132,45 C170,45 170,120 200,125" />
        <L d="M132,89 L200,132" />
        <L d="M132,133 L200,139" />
        <L d="M132,177 L200,146" />
        <L d="M132,221 C170,221 170,155 200,152" />
        <L d="M132,265 C175,265 175,160 200,158" />
        <L d="M275,62 L275,100" />
        <L d="M275,200 L275,164" />
        <L d="M350,132 L400,132" />
        <L d="M550,90 L600,45" />
        <L d="M550,110 L600,101" />
        <L d="M550,140 L600,157" />
        <L d="M550,170 L600,213" />
        <L d="M750,213 L810,213" wind />
        <L d="M600,112 C580,112 578,124 578,140 L578,258 C578,272 588,278 600,280" />
        <L d="M550,287 L600,287" />
        <L d="M750,45 C798,45 798,357 750,357" />
        <L d="M810,317 L750,295" />
        <L d="M810,325 L750,355" />
        <L d="M412,200 C388,214 386,330 400,352" />
      </svg>
    </div>
  );
}
