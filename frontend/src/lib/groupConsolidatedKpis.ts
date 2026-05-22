/**
 * Calculs KPI consolidés groupe (masse salariale, charges, effectifs).
 */

export const CHARGE_RATE_WARNING = 40;
export const CHARGE_RATE_CRITICAL = 45;

export interface CompanyStatsLike {
  company_id: string;
  company_name: string;
  siret?: string;
  total_employee_count: number;
  employee_count: number;
  rh_count: number;
  payslip_count: number;
  gross_salary: number;
  net_salary: number;
  employer_charges: number;
}

export interface CompanyKpiRow {
  company_id: string;
  company_name: string;
  total_employee_count: number;
  payslip_count: number;
  chargeRate: number;
  netRetentionRate: number;
  totalCostPerEmployee: number;
  grossPerEmployee: number;
  chargesPerEmployee: number;
  rhRatio: number;
  costPerPayslip: number;
  totalEmployerCost: number;
}

export interface DistributionStats {
  min: number;
  max: number;
  avg: number;
  median: number;
  spread: number;
}

export function totalEmployerCost(company: CompanyStatsLike): number {
  return company.gross_salary + company.employer_charges;
}

export function chargeRatePercent(company: CompanyStatsLike): number {
  return company.gross_salary > 0
    ? (company.employer_charges / company.gross_salary) * 100
    : 0;
}

export function computeCompanyKpis(company: CompanyStatsLike): CompanyKpiRow {
  const chargeRate = chargeRatePercent(company);
  const netRetentionRate =
    company.gross_salary > 0 ? (company.net_salary / company.gross_salary) * 100 : 0;
  const totalCostPerEmployee =
    company.total_employee_count > 0
      ? totalEmployerCost(company) / company.total_employee_count
      : 0;
  const grossPerEmployee =
    company.total_employee_count > 0
      ? company.gross_salary / company.total_employee_count
      : 0;
  const chargesPerEmployee =
    company.total_employee_count > 0
      ? company.employer_charges / company.total_employee_count
      : 0;
  const rhRatio =
    company.total_employee_count > 0
      ? (company.rh_count / company.total_employee_count) * 100
      : 0;
  const costPerPayslip =
    company.payslip_count > 0 ? totalEmployerCost(company) / company.payslip_count : 0;

  return {
    company_id: company.company_id,
    company_name: company.company_name,
    total_employee_count: company.total_employee_count,
    payslip_count: company.payslip_count,
    chargeRate,
    netRetentionRate,
    totalCostPerEmployee,
    grossPerEmployee,
    chargesPerEmployee,
    rhRatio,
    costPerPayslip,
    totalEmployerCost: totalEmployerCost(company),
  };
}

export function computeDistribution(values: number[]): DistributionStats {
  if (values.length === 0) {
    return { min: 0, max: 0, avg: 0, median: 0, spread: 0 };
  }
  const sorted = [...values].sort((a, b) => a - b);
  const min = sorted[0];
  const max = sorted[sorted.length - 1];
  const avg = sorted.reduce((a, b) => a + b, 0) / sorted.length;
  const median =
    sorted.length % 2 === 0
      ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
      : sorted[Math.floor(sorted.length / 2)];

  return { min, max, avg, median, spread: max - min };
}

export function percentDelta(current: number, previous: number): number | null {
  if (previous === 0) return current === 0 ? 0 : null;
  return ((current - previous) / previous) * 100;
}

export function chargeRateColorClass(rate: number): string {
  if (rate > CHARGE_RATE_CRITICAL) return "text-red-600";
  if (rate > CHARGE_RATE_WARNING) return "text-amber-600";
  return "text-green-600";
}

export interface ConsolidatedTotalsLike {
  total_employees: number;
  total_employees_excluding_rh: number;
  total_rh: number;
  total_payslip_count: number;
  total_gross_salary: number;
  total_net_salary: number;
  total_employer_charges: number;
  average_gross_per_company: number;
  average_employees_per_company: number;
  company_count?: number;
}

export function totalsEmployerCost(totals: ConsolidatedTotalsLike): number {
  return totals.total_gross_salary + totals.total_employer_charges;
}

export function groupChargeRate(totals: ConsolidatedTotalsLike): number {
  return totals.total_gross_salary > 0
    ? (totals.total_employer_charges / totals.total_gross_salary) * 100
    : 0;
}
