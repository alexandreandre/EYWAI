import apiClient from "@/api/apiClient";

export type CycleStatus = "brouillon" | "en_cours" | "clos";

export interface ItemsAIntegrer {
  ndf: number;
  absences: number;
  primes: number;
  avances: number;
  total: number;
}

export interface PayrollAnalyticsSummary {
  period: string;
  statut_cycle: CycleStatus;
  nb_bulletins_valides: number;
  nb_bulletins_attendus: number;
  anomalies_bloquantes: number;
  anomalies_warnings: number;
  masse_brute: number;
  cout_employeur_total: number;
  net_verse: number;
  effectif_paye: number;
  effectif_actif: number;
  delta_brut_m1_pct: number | null;
  delta_cout_m1_pct: number | null;
  items_a_integrer: ItemsAIntegrer;
  cycle_closed_at: string | null;
}

export interface PayrollTrendPoint {
  period: string;
  masse_brute: number;
  cotisations_salariales: number;
  cotisations_patronales: number;
  net_verse: number;
  cout_employeur: number;
  effectif_paye: number;
  is_closed: boolean;
}

export interface PayrollAnalyticsTrends {
  end_period: string;
  months: number;
  points: PayrollTrendPoint[];
}

export interface PayrollBreakdownItem {
  key: string;
  label: string;
  masse_brute: number;
  cout_employeur: number;
  effectif: number;
}

export type BreakdownGroupBy = "team" | "service" | "contract_type";

export interface PayrollAnalyticsBreakdown {
  period: string;
  group_by: BreakdownGroupBy;
  items: PayrollBreakdownItem[];
  total_masse_brute: number;
}

export interface PayrollPeriodItem {
  year: number;
  month: number;
  period: string;
  status: "open" | "closed" | "locked";
  closed_at: string | null;
  closed_by: string | null;
}

export interface PayrollPeriodsResponse {
  year: number;
  periods: PayrollPeriodItem[];
}

function companyHeaders(companyId?: string | null) {
  return companyId && companyId.length > 0
    ? { "X-Active-Company": companyId }
    : undefined;
}

function teamParams(teamIds?: string[]) {
  const params: Record<string, string | string[]> = {};
  if (teamIds?.length) {
    params.team_ids = teamIds;
  }
  return params;
}

export async function getPayrollAnalyticsSummary(
  companyId: string | null | undefined,
  period: string,
  teamIds?: string[],
): Promise<PayrollAnalyticsSummary> {
  const { data } = await apiClient.get<PayrollAnalyticsSummary>(
    "/api/payroll/analytics/summary",
    {
      headers: companyHeaders(companyId),
      params: { period, ...teamParams(teamIds) },
    },
  );
  return data;
}

export async function getPayrollAnalyticsTrends(
  companyId: string | null | undefined,
  opts?: { months?: number; endPeriod?: string; teamIds?: string[] },
): Promise<PayrollAnalyticsTrends> {
  const { data } = await apiClient.get<PayrollAnalyticsTrends>(
    "/api/payroll/analytics/trends",
    {
      headers: companyHeaders(companyId),
      params: {
        months: opts?.months ?? 12,
        ...(opts?.endPeriod ? { end_period: opts.endPeriod } : {}),
        ...teamParams(opts?.teamIds),
      },
    },
  );
  return data;
}

export async function getPayrollAnalyticsBreakdown(
  companyId: string | null | undefined,
  period: string,
  groupBy: BreakdownGroupBy,
  teamIds?: string[],
): Promise<PayrollAnalyticsBreakdown> {
  const { data } = await apiClient.get<PayrollAnalyticsBreakdown>(
    "/api/payroll/analytics/breakdown",
    {
      headers: companyHeaders(companyId),
      params: { period, group_by: groupBy, ...teamParams(teamIds) },
    },
  );
  return data;
}

export async function getPayrollPeriods(
  companyId: string | null | undefined,
  year: number,
): Promise<PayrollPeriodsResponse> {
  const { data } = await apiClient.get<PayrollPeriodsResponse>("/api/payroll/periods", {
    headers: companyHeaders(companyId),
    params: { year },
  });
  return data;
}
