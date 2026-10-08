import { resolve } from 'node:path';
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { Snapshot } from '../types/contract';
import { SiteSheet } from '../screens/SiteSheet';
import { Home } from '../screens/Home';
import { Atlas } from '../screens/Atlas';

const raw = JSON.parse(readFileSync(resolve(process.cwd(), 'public/data/snapshot.json'), 'utf-8')) as Snapshot;

function withData(path: string, el: React.ReactNode, route: string) {
  const qc = new QueryClient();
  const siteById = Object.fromEntries(raw.sites.map((s) => [s.site_id, s]));
  const by = <T extends { site_id: string }>(xs: T[]) => Object.fromEntries(raw.sites.map((s) => [s.site_id, xs.filter((x) => x.site_id === s.site_id)]));
  qc.setQueryData(['snapshot'], { ...raw, siteById, detBySite: by(raw.detections), fdBySite: by(raw.fire_days), epBySite: by(raw.episodes), liveError: null });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={el} /></Routes></MemoryRouter>
    </QueryClientProvider>,
  );
}

function expectReceipts(container: HTMLElement) {
  const metrics = container.querySelectorAll('[data-metric]');
  expect(metrics.length).toBeGreaterThan(0);
  metrics.forEach((m) => {
    expect(m.querySelector('[data-tier]'), m.textContent ?? '').not.toBeNull();
    expect(m.querySelector('[data-receipt]') ?? (m.hasAttribute('data-receipt') ? m : null), m.textContent ?? '').not.toBeNull();
  });
  return metrics.length;
}

describe('every number has a tier and a receipt', () => {
  it('Fire Record', () => {
    const { container } = withData('/site/bhalswa', <SiteSheet />, '/site/:id');
    expect(expectReceipts(container)).toBeGreaterThan(8);
  });
  it('years without detections say so (never zero-filled bars)', () => {
    withData('/site/okhla', <SiteSheet />, '/site/:id');
    expect(screen.getAllByText('no detections').length).toBeGreaterThan(3);
  });
  it('Smoke Days answer', async () => {
    const { container } = withData('/?q=Bhalaswa&year=all', <Home />, '/');
    await waitFor(() => expect(container.querySelector('.answer')).not.toBeNull());
    expectReceipts(container);
  });
  it('Atlas ledger', () => {
    const { container } = withData('/sites', <Atlas />, '/sites');
    expectReceipts(container);
    expect(container.querySelectorAll('[data-tier]').length).toBeGreaterThan(2);
  });
});
