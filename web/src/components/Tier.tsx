import { useId, useState, type ReactNode } from 'react';
import { useT } from '../i18n';
import type { MetricTier } from '../types/contract';
import './tier.css';

export function TierChip({ tier }: { tier: MetricTier }) {
  const { t } = useT();
  return (
    <span className={`tier tier-${tier.toLowerCase()}`} data-tier={tier} title={t(`tier.${tier}`)}>
      <span className="tier-word">{tier}</span>
    </span>
  );
}

export interface ReceiptData { source: string; method: string; date: string; href?: string }

/** A number with its tier chip and an expandable receipt (source, method, date, tier). */
export function Metric({
  value, unit, tier, receipt, label, big = false, children,
}: {
  value: ReactNode; unit?: ReactNode; tier: MetricTier; receipt: ReceiptData; label?: ReactNode; big?: boolean; children?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const { t } = useT();
  return (
    <div className={`metric${big ? ' metric-big' : ''}`} data-metric>
      {label && <div className="label metric-label">{label}</div>}
      <div className="metric-row">
        <span className="num metric-value">{value}</span>
        {unit && <span className="metric-unit">{unit}</span>}
        <TierChip tier={tier} />
        <button className="receipt-btn mono" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} data-receipt-toggle>
          <span aria-hidden>{open ? '−' : '+'}</span>
          <span className="sr-only">{t('receipt.source')}</span>
        </button>
      </div>
      {children}
      <dl id={id} className="receipt" data-receipt hidden={!open}>
        <dt>{t('receipt.source')}</dt><dd>{receipt.href ? <a href={receipt.href} target="_blank" rel="noreferrer">{receipt.source}</a> : receipt.source}</dd>
        <dt>{t('receipt.method')}</dt><dd>{receipt.method}</dd>
        <dt>{t('receipt.date')}</dt><dd className="mono">{receipt.date}</dd>
        <dt>{t('receipt.tier')}</dt><dd>{t(`tier.${tier}`)}</dd>
      </dl>
    </div>
  );
}
