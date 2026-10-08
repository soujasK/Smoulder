import { useT } from '../i18n';
import { dateLabel, MONTH_INITIALS } from '../lib/format';

export type CellKind = 'fill' | 'outline' | 'low';

export interface CalendarProps {
  year: number;
  cells: Record<string, CellKind>; // ISO date -> style
  ticks?: Set<string>; // news-reported dates (thin tick above the cell)
  highlight?: string | null;
  onPick?: (date: string) => void;
  caption: string;
  legend: { fill: string; outline?: string; tick?: string; low?: string };
  /** a date up to which data exists; later cells are drawn as "no data" */
  through?: string;
  start?: string;
}

const CELL = 11;
const GAP = 2;
const LEFT = 26;
const TOP = 14;

function daysIn(y: number, m: number) { return new Date(Date.UTC(y, m + 1, 0)).getUTCDate(); }

/** Year calendar: 12 rows (months) x 31 columns (days). SVG, prints cleanly. */
export function Calendar({ year, cells, ticks, highlight, onPick, caption, legend, through, start }: CalendarProps) {
  const { lang } = useT();
  const W = LEFT + 31 * (CELL + GAP);
  const H = TOP + 12 * (CELL + GAP + 3);
  const items: React.ReactNode[] = [];
  for (let m = 0; m < 12; m++) {
    const y0 = TOP + m * (CELL + GAP + 3);
    items.push(<text key={`m${m}`} x={0} y={y0 + CELL - 1} className="cal-m">{MONTH_INITIALS[lang][m]}</text>);
    for (let d = 1; d <= daysIn(year, m); d++) {
      const iso = `${year}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const x = LEFT + (d - 1) * (CELL + GAP);
      const kind = cells[iso];
      const noData = (through && iso > through) || (start && iso < start);
      const cls = noData ? 'cal-c cal-nodata' : kind ? `cal-c cal-${kind}` : 'cal-c';
      const label = `${dateLabel(iso, lang)}${kind ? ` · ${kind === 'fill' ? legend.fill : kind === 'outline' ? legend.outline : legend.low}` : ''}${ticks?.has(iso) ? ` · ${legend.tick}` : ''}`;
      items.push(
        <g key={iso}>
          <rect x={x + 0.5} y={y0 + 0.5} width={CELL - 1} height={CELL - 1} className={cls + (highlight === iso ? ' cal-hi' : '')}
            tabIndex={kind && onPick ? 0 : -1} role={kind && onPick ? 'button' : undefined} aria-label={kind || ticks?.has(iso) ? label : undefined}
            onClick={kind && onPick ? () => onPick(iso) : undefined}
            onKeyDown={kind && onPick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onPick(iso); } } : undefined}>
            <title>{label}</title>
          </rect>
          {ticks?.has(iso) && <line x1={x + CELL / 2} x2={x + CELL / 2} y1={y0 - 3.5} y2={y0 - 0.5} className="cal-tick" />}
        </g>,
      );
    }
  }
  for (const d of [1, 10, 20, 31]) items.push(<text key={`d${d}`} x={LEFT + (d - 1) * (CELL + GAP) + CELL / 2} y={8} className="cal-d" textAnchor="middle">{d}</text>);
  return (
    <figure className="cal">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W * 1.6 }} role="img" aria-label={caption}>{items}</svg>
      <figcaption className="cal-legend tiny">
        <span><svg width="10" height="10" aria-hidden><rect x=".5" y=".5" width="9" height="9" className="cal-c cal-fill" /></svg> {legend.fill}</span>
        {legend.outline && <span><svg width="10" height="10" aria-hidden><rect x=".5" y=".5" width="9" height="9" className="cal-c cal-outline" /></svg> {legend.outline}</span>}
        {legend.low && <span><svg width="10" height="10" aria-hidden><rect x=".5" y=".5" width="9" height="9" className="cal-c cal-low" /></svg> {legend.low}</span>}
        {legend.tick && <span><svg width="10" height="10" aria-hidden><line x1="5" x2="5" y1="0" y2="6" className="cal-tick" /></svg> {legend.tick}</span>}
      </figcaption>
    </figure>
  );
}
