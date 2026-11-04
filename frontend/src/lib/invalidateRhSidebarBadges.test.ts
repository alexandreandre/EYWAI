import { QueryClient, QueryObserver } from '@tanstack/react-query';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { rafraichirBadgesAnciens } from './invalidateRhSidebarBadges';

describe('rafraichirBadgesAnciens — un changement d’écran ne relance plus tout', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  /** Deux compteurs (30 s et 5 min, comme la barre) et une requête qui n'en est pas une. */
  function client() {
    vi.useFakeTimers({ now: new Date('2026-11-04T08:00:00Z') });
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const lectures: Record<string, number> = {};
    const observer = (queryKey: unknown[], staleTime: number) => {
      const nom = String(queryKey[0]);
      lectures[nom] = 0;
      qc.setQueryData(queryKey, 1);
      const o = new QueryObserver(qc, {
        queryKey,
        queryFn: () => {
          lectures[nom] += 1;
          return 1;
        },
        staleTime,
      });
      o.subscribe(() => undefined);
    };
    observer(['dashboard', 'all', 'sidebar-badges', 'c1'], 30_000);
    observer(['schedules', 'sidebar-badges', 'c1', 2026, 10], 5 * 60_000);
    observer(['payslips', 'c1'], Infinity);
    return { qc, lectures };
  }

  it('des compteurs encore frais ne sont pas relus', async () => {
    const { qc, lectures } = client();
    await rafraichirBadgesAnciens(qc);
    expect(lectures).toEqual({ dashboard: 0, schedules: 0, payslips: 0 });
  });

  it('chaque compteur suit son propre délai, et les autres requêtes ne bougent pas', async () => {
    const { qc, lectures } = client();
    vi.advanceTimersByTime(31_000);
    await rafraichirBadgesAnciens(qc);
    // Le compteur des calendriers (5 min) reste : c'est lui qui coûte un appel par salarié.
    expect(lectures).toEqual({ dashboard: 1, schedules: 0, payslips: 0 });
    vi.advanceTimersByTime(270_000);
    await rafraichirBadgesAnciens(qc);
    expect(lectures).toEqual({ dashboard: 2, schedules: 1, payslips: 0 });
  });
});
