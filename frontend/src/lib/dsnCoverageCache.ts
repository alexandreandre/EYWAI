import type { QueryClient } from '@tanstack/react-query';

import type {
  DsnCoverage,
  DsnCoverageAdminMatrixResponse,
  DsnCoverageMatrixCompany,
  DsnCoverageStatus,
  DsnCoverageTimelineMonth,
  DsnImportBatchDetail,
} from '@/api/dsnImport';

/** Ne renvoie la couverture que si elle correspond à la filiale demandée. */
export function scopedDsnCoverage(
  coverage: DsnCoverage | undefined,
  companyId: string,
): DsnCoverage | undefined {
  if (!companyId || !coverage) return undefined;
  return coverage.company_id === companyId ? coverage : undefined;
}

/** Invalide les caches couverture DSN après révocation ou reset onboarding. */
export function invalidateDsnCoverageForCompany(
  queryClient: QueryClient,
  companyId: string,
): void {
  if (!companyId) return;
  void queryClient.invalidateQueries({ queryKey: ['dsn-coverage', companyId] });
  void queryClient.invalidateQueries({ queryKey: ['company-setup-status', companyId] });
  void queryClient.invalidateQueries({ queryKey: ['dsn-admin-matrix'] });
  void queryClient.invalidateQueries({ queryKey: ['dsn-admin-late-summary'] });
}

export function expandPeriodRange(
  periodMin?: string | null,
  periodMax?: string | null,
): string[] {
  if (!periodMin) return [];
  const start = parsePeriod(periodMin);
  const end = parsePeriod(periodMax ?? periodMin);
  if (!start || !end) return [periodMin];
  const out: string[] = [];
  let [y, m] = start;
  const [ey, em] = end;
  while (y < ey || (y === ey && m <= em)) {
    out.push(`${y}-${String(m).padStart(2, '0')}`);
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
  }
  return out;
}

function parsePeriod(period: string): [number, number] | null {
  const [y, m] = period.split('-');
  const yi = parseInt(y, 10);
  const mi = parseInt(m, 10);
  if (!yi || !mi || mi < 1 || mi > 12) return null;
  return [yi, mi];
}

export function extractCommittedCoverageFromBatch(
  detail: Pick<DsnImportBatchDetail, 'batch' | 'summary'>,
): { companyId: string; periods: string[] } | null {
  const summary = detail.summary ?? {};
  const batch = detail.batch;
  const companyId =
    (summary.target_company_id as string | undefined)
    ?? ((summary.commit_report as { target_company_id?: string } | undefined)?.target_company_id);
  if (!companyId) return null;

  const periods = new Set<string>();
  const committed = summary.periods_committed;
  if (Array.isArray(committed)) {
    committed.forEach((p) => {
      if (p) periods.add(String(p));
    });
  }
  const stats = (summary.commit_report as { stats?: { created?: number; updated?: number } } | undefined)
    ?.stats;
  const hadImportWork = ((stats?.created ?? 0) + (stats?.updated ?? 0)) > 0;
  if (periods.size === 0 && hadImportWork) {
    expandPeriodRange(
      batch.period_min ?? (summary.period_min as string | undefined),
      batch.period_max ?? (summary.period_max as string | undefined),
    ).forEach((p) => periods.add(p));
  }

  if (periods.size === 0) return null;
  return { companyId, periods: [...periods].sort() };
}

export function resolveNextImportPeriod(coverage: {
  timeline?: DsnCoverageTimelineMonth[];
  gaps?: string[];
}): string | null {
  const timeline = coverage.timeline ?? [];
  const missing = timeline
    .filter((m) => m.state === 'missing' && m.period)
    .map((m) => m.period)
    .sort();
  if (missing.length > 0) return missing[0];
  const gaps = [...(coverage.gaps ?? [])].map(String).sort();
  return gaps[0] ?? null;
}

function recomputeCompanyStatus(
  timeline: DsnCoverageTimelineMonth[],
  monthsCovered: string[],
  expectedLastPeriod: string,
  previous: DsnCoverageStatus,
): DsnCoverageStatus {
  if (previous === 'not_applicable' && monthsCovered.length === 0) {
    return previous;
  }
  const gaps = timeline.filter(
    (m) => m.state === 'missing' && m.period <= expectedLastPeriod,
  );
  if (monthsCovered.length === 0) {
    return previous === 'not_applicable' ? 'not_applicable' : 'never';
  }
  if (monthsCovered.includes(expectedLastPeriod) && gaps.length === 0) {
    return 'ok';
  }
  if (!monthsCovered.includes(expectedLastPeriod)) {
    return previous === 'late' ? 'late' : 'missing';
  }
  if (gaps.length > 0) return 'missing';
  return 'ok';
}

function patchMatrixCompany(
  company: DsnCoverageMatrixCompany,
  periods: string[],
): DsnCoverageMatrixCompany {
  const periodSet = new Set(periods);
  const monthsCovered = [...new Set([...company.months_covered, ...periods])].sort();
  const timeline = company.timeline.map((month) => {
    if (!periodSet.has(month.period) || month.state === 'future') return month;
    return { ...month, state: 'covered' as const };
  });
  const gapsCount = timeline.filter(
    (m) => m.state === 'missing' && m.period <= company.expected_last_period,
  ).length;
  const lastPeriod = monthsCovered[monthsCovered.length - 1] ?? company.last_period;
  const status = recomputeCompanyStatus(
    timeline,
    monthsCovered,
    company.expected_last_period,
    company.status,
  );
  return {
    ...company,
    months_covered: monthsCovered,
    timeline,
    gaps_count: gapsCount,
    last_period: lastPeriod,
    status,
    last_import_at: new Date().toISOString(),
  };
}

function patchSingleCoverage(coverage: DsnCoverage, periods: string[]): DsnCoverage {
  const periodSet = new Set(periods);
  const monthsCovered = [...new Set([...coverage.months_covered, ...periods])].sort();
  const timeline = coverage.timeline.map((month) => {
    if (!periodSet.has(month.period) || month.state === 'future') return month;
    return { ...month, state: 'covered' as const };
  });
  const gaps = timeline
    .filter((m) => m.state === 'missing' && m.period <= coverage.expected_last_period)
    .map((m) => m.period);
  const status = recomputeCompanyStatus(
    timeline,
    monthsCovered,
    coverage.expected_last_period,
    coverage.status,
  );
  const nextImportPeriod = resolveNextImportPeriod({ timeline, gaps });
  return {
    ...coverage,
    months_covered: monthsCovered,
    timeline,
    gaps,
    next_import_period: nextImportPeriod,
    last_period: monthsCovered[monthsCovered.length - 1] ?? coverage.last_period,
    status,
    last_import_at: new Date().toISOString(),
  };
}

export function patchDsnCoverageMatrixCache(
  queryClient: QueryClient,
  patch: { companyId: string; periods: string[] },
): void {
  const { companyId, periods } = patch;
  if (!periods.length) return;

  const matrixQueries = queryClient.getQueriesData<DsnCoverageAdminMatrixResponse>({
    queryKey: ['dsn-admin-matrix'],
  });
  for (const [queryKey, data] of matrixQueries) {
    if (!data?.companies) continue;
    const year = typeof queryKey[1] === 'number' ? queryKey[1] : null;
    const relevantPeriods = year
      ? periods.filter((p) => p.startsWith(`${year}-`))
      : periods;
    if (!relevantPeriods.length) continue;
    queryClient.setQueryData<DsnCoverageAdminMatrixResponse>(queryKey, {
      ...data,
      companies: data.companies.map((company) =>
        company.company_id === companyId
          ? patchMatrixCompany(company, relevantPeriods)
          : company,
      ),
    });
  }

  const coverageKey = ['dsn-coverage', companyId] as const;
  const coverage = queryClient.getQueryData<DsnCoverage>(coverageKey);
  if (coverage) {
    queryClient.setQueryData(coverageKey, patchSingleCoverage(coverage, periods));
  }
}

export async function refreshDsnCoverageQueries(
  queryClient: QueryClient,
  options?: { includeMatrix?: boolean },
): Promise<void> {
  const tasks = [
    queryClient.refetchQueries({ queryKey: ['dsn-admin-late-summary'] }),
    queryClient.refetchQueries({ queryKey: ['dsn-import-batches'] }),
    queryClient.refetchQueries({ queryKey: ['dsn-import-batches-pending'] }),
  ];
  if (options?.includeMatrix) {
    tasks.push(queryClient.refetchQueries({ queryKey: ['dsn-admin-matrix'] }));
    tasks.push(queryClient.refetchQueries({ queryKey: ['dsn-coverage'] }));
  }
  await Promise.all(tasks);
}

function invalidateCompanySetupAfterDsnCommit(
  queryClient: QueryClient,
  companyId: string,
): void {
  void queryClient.invalidateQueries({ queryKey: ['company-setup-status', companyId] });
}

export async function applyDsnImportCommitted(
  queryClient: QueryClient,
  detail: DsnImportBatchDetail,
): Promise<void> {
  const coverage = extractCommittedCoverageFromBatch(detail);
  if (coverage) {
    patchDsnCoverageMatrixCache(queryClient, coverage);
    invalidateCompanySetupAfterDsnCommit(queryClient, coverage.companyId);
    const coverageKey = ['dsn-coverage', coverage.companyId] as const;
    if (!queryClient.getQueryData(coverageKey)) {
      void queryClient.invalidateQueries({ queryKey: coverageKey });
    }
  }
  await refreshDsnCoverageQueries(queryClient, { includeMatrix: false });
  if (coverage) {
    window.setTimeout(() => {
      void queryClient.refetchQueries({ queryKey: ['dsn-coverage', coverage.companyId] });
      void queryClient.refetchQueries({ queryKey: ['dsn-admin-matrix'] });
      void queryClient.invalidateQueries({ queryKey: ['company-setup-status', coverage.companyId] });
    }, 1500);
  }
}
