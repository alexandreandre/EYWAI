import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { DsnCoverageMatrixCompany, DsnCoverageTimelineMonth } from '@/api/dsnImport';
import { TooltipProvider } from '@/components/ui/tooltip';
import { CompanyCoverageRow } from '../components/DsnCoverageMatrix';
import { DsnCoverageTimeline } from '../components/DsnCoverageTimeline';
import { countExpectedDsnMonths, dsnMatrixDisplayStatus, dsnMonthActionState } from './coveragePresentation';

const timeline: DsnCoverageTimelineMonth[] = Array.from({ length: 12 }, (_, i) => ({
  period: `2026-${String(i + 1).padStart(2, '0')}`,
  month: i + 1,
  state: i < 9 ? 'covered' : 'native',
}));

const company: DsnCoverageMatrixCompany = {
  company_id: 'societe-test', company_name: 'Société test',
  dsn_sync_mode: 'transition', status: 'ok', expected_last_period: '2026-09',
  import_cutoff_period: '2026-09', months_covered: timeline.slice(0, 10).map((m) => m.period),
  timeline, gaps_count: 0,
};

describe('couverture DSN après reprise', () => {
  it('un import optionnel reste consultable et ne gonfle pas les neuf mois attendus', () => {
    expect(countExpectedDsnMonths(timeline)).toEqual({ covered: 9, expected: 9, pct: 100 });
    expect(dsnMonthActionState(timeline[9], company.months_covered)).toBe('covered');
    expect(dsnMonthActionState(timeline[10], company.months_covered)).toBeNull();
  });

  it('un mois manquant garde son action et un futur reçu peut être consulté', () => {
    expect(dsnMonthActionState({ ...timeline[8], state: 'missing' }, [])).toBe('missing');
    expect(dsnMonthActionState({ ...timeline[11], state: 'future' }, [])).toBeNull();
    expect(dsnMonthActionState({ ...timeline[11], state: 'future' }, ['2026-12'])).toBe('covered');
  });

  it('ne transforme pas Paie Martine en Retard quand aucun import n’est attendu sur l’année', () => {
    const native: DsnCoverageMatrixCompany = { ...company, status: 'not_applicable', timeline: timeline.map((m) => ({ ...m, state: 'native' as const })), months_covered: [] };
    expect(dsnMatrixDisplayStatus(native)).toBe('not_applicable');
    expect(dsnMatrixDisplayStatus({ ...native, status: 'missing' })).toBe('missing');
    expect(dsnMatrixDisplayStatus({ ...native, timeline: [{ ...timeline[0], state: 'missing' }] })).toBe('missing');
  });

  it('la matrice expose le mois Martine déjà reçu comme une action accessible', () => {
    const html = renderToStaticMarkup(createElement(TooltipProvider, null,
      createElement(CompanyCoverageRow, { company, onCellClick: () => undefined }),
    ));
    expect(html).toContain('aria-label="Octobre 2026-10 — Paie Martine - import externe non attendu — DSN déjà importée"');
    expect(html).toContain('role="button"');
    expect(html.replace(/<[^>]+>/g, '')).toContain('9/9');
  });

  it('la frise distingue un import optionnel reçu d’un mois Martine sans import', () => {
    const html = renderToStaticMarkup(createElement(DsnCoverageTimeline, { timeline, importedPeriods: company.months_covered }));
    expect(html).toContain('2026-10 — Paie Martine - import externe non attendu — DSN déjà importée');
    expect(html).not.toContain('2026-11 — Paie Martine - import externe non attendu — DSN déjà importée');
  });
});
