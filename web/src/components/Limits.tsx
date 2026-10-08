import { useT } from '../i18n';

export function Limits() {
  const { t } = useT();
  return (
    <aside className="limits" aria-labelledby="limits-h">
      <h3 id="limits-h">{t('site.limits')}</h3>
      <ul>{[1, 2, 3, 4, 5, 6, 7].map((i) => <li key={i}>{t(`limits.${i}`)}</li>)}</ul>
    </aside>
  );
}
