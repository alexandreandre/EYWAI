import { QueryClient } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { rafraichirBadgesAnciens } from './invalidateRhSidebarBadges';

describe('rafraichirBadgesAnciens — un changement d’écran ne relance plus tout', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  function client() {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(['schedules', 'sidebar-badges', 'c1', 2026, 10], 3);
    qc.setQueryData(['dashboard', 'all', 'sidebar-badges', 'c1'], {});
    qc.setQueryData(['payslips', 'c1'], []);
    return qc;
  }
  const invalides = (qc: QueryClient) =>
    qc
      .getQueryCache()
      .getAll()
      .filter((q) => q.state.isInvalidated)
      .map((q) => q.queryKey[0]);

  it('des compteurs lus il y a moins de 30 s ne sont pas relus', async () => {
    const qc = client();
    await rafraichirBadgesAnciens(qc);
    expect(invalides(qc)).toEqual([]);
  });

  it('des compteurs plus anciens sont relus, et eux seuls (pas les autres requêtes)', async () => {
    vi.useFakeTimers({ now: Date.now() });
    const qc = client();
    vi.setSystemTime(Date.now() + 31_000);
    await rafraichirBadgesAnciens(qc);
    expect(invalides(qc).sort()).toEqual(['dashboard', 'schedules']);
  });
});
