import type { DsnCoverageMatrixCompany, DsnCoverageTimelineMonth } from '@/api/dsnImport';

export function countExpectedDsnMonths(timeline: DsnCoverageTimelineMonth[]) {
  const applicable = timeline.filter((m) => m.state !== 'future' && m.state !== 'native');
  const covered = applicable.filter((m) => m.state === 'covered').length;
  const expected = applicable.length;
  return { covered, expected, pct: expected > 0 ? Math.round((covered / expected) * 100) : 0 };
}

export function dsnMatrixDisplayStatus(company: DsnCoverageMatrixCompany) {
  const { covered, expected } = countExpectedDsnMonths(company.timeline);
  if ((company.status === 'not_applicable' || company.status === 'never') && expected > 0 && covered === 0) {
    return 'missing';
  }
  return company.status;
}

/** Un import optionnel reçu reste consultable sans rendre le mois attendu. */
export function isDsnMonthImported(month: DsnCoverageTimelineMonth, importedPeriods: readonly string[]) {
  return month.state === 'covered' || importedPeriods.includes(month.period);
}

export function dsnMonthActionState(
  month: DsnCoverageTimelineMonth,
  importedPeriods: readonly string[],
): 'covered' | 'missing' | null {
  if (isDsnMonthImported(month, importedPeriods)) return 'covered';
  return month.state === 'missing' ? 'missing' : null;
}
