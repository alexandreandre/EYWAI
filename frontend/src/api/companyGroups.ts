import apiClient from "@/api/apiClient";

export interface GroupCompany {
  id: string;
  company_name: string;
  siret?: string | null;
  is_active?: boolean;
}

export interface GroupDetails {
  id: string;
  group_name: string;
  siren?: string | null;
  description?: string | null;
  logo_url?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  companies: GroupCompany[];
}

export interface CompanyStats {
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
  payroll_source?: 'payslip' | 'dsn' | 'none';
  payroll_source_label?: string;
  payroll_partial?: boolean;
}

export interface ConsolidatedStats {
  metadata: {
    reference_year: number;
    reference_month: number;
    generated_at: string;
    company_count: number;
    period_start_year?: number;
    period_start_month?: number;
    period_end_year?: number;
    period_end_month?: number;
    has_mixed_sources?: boolean;
  };
  totals: {
    total_employees: number;
    total_employees_excluding_rh: number;
    total_rh: number;
    total_payslip_count: number;
    total_gross_salary: number;
    total_net_salary: number;
    total_employer_charges: number;
    average_gross_per_company: number;
    average_employees_per_company: number;
  };
  by_company: CompanyStats[];
  comparison?: {
    totals: ConsolidatedStats["totals"];
    by_company: CompanyStats[];
  };
}

export interface EvolutionDataPoint {
  company_id: string;
  company_name: string;
  year: number;
  month: number;
  total_gross: number;
  total_net: number;
  total_employer_charges: number;
  employee_count: number;
}

export type CompareToMode = "off" | "previous_month" | "previous_year" | "ytd_previous_year";

export interface ConsolidatedStatsParams {
  year?: number;
  month?: number;
  start_year?: number;
  start_month?: number;
  end_year?: number;
  end_month?: number;
  compare_to?: CompareToMode;
}

export async function fetchGroupDetails(groupId: string): Promise<GroupDetails> {
  const { data } = await apiClient.get<GroupDetails>(`/api/company-groups/${groupId}`);
  return data;
}

export async function fetchConsolidatedStats(
  groupId: string,
  params: ConsolidatedStatsParams,
): Promise<ConsolidatedStats> {
  const { data } = await apiClient.get<ConsolidatedStats>(
    `/api/company-groups/${groupId}/consolidated-stats`,
    { params },
  );
  return data;
}

export async function fetchPayrollEvolution(
  groupId: string,
  startYear: number,
  startMonth: number,
  endYear: number,
  endMonth: number,
): Promise<EvolutionDataPoint[]> {
  const { data } = await apiClient.get<EvolutionDataPoint[]>(
    `/api/company-groups/${groupId}/payroll-evolution`,
    {
      params: {
        start_year: startYear,
        start_month: startMonth,
        end_year: endYear,
        end_month: endMonth,
      },
    },
  );
  return data ?? [];
}
