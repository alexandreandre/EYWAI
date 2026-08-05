import apiClient from "@/api/apiClient";
import { downloadBlob } from '@/lib/downloadBlob';
import type { DsnCoverage, DsnSyncMode } from '@/api/dsnImport';
import type { FrenchPublicHolidayId } from '@/lib/frenchPublicHolidays';

import type { PayrollSource } from '@/features/dashboard/types';

export interface MonthlyEvolution {
  month: string;
  masse_salariale_brute: number;
  net_verse: number;
  charges_totales: number;
  cout_total_employeur: number;
  payroll_source?: PayrollSource;
  payroll_source_label?: string;
  payroll_partial?: boolean;
}

export interface CompanyKPIs {
  total_employees: number;
  last_month_gross_salary: number;
  last_month_net_salary: number;
  last_month_employer_charges: number;
  last_month_employee_charges: number;
  last_month_total_cost: number;
  last_month_total_charges: number;
  annual_gross_salary: number;
  annual_total_cost: number;
  contract_distribution: Record<string, number>;
  job_distribution: Record<string, number>;
  new_hires_last_30_days: number;
  payroll_tax_rate: number;
  average_cost_per_employee: number;
  evolution_12_months: MonthlyEvolution[];
  evolution_24_months?: MonthlyEvolution[];
  previous_year_gross_salary?: number;
  previous_year_total_cost?: number;
  payroll_source?: PayrollSource;
  payroll_source_label?: string;
  payroll_partial?: boolean;
  payroll_has_mixed_sources?: boolean;
  last_month_payroll_source?: PayrollSource;
}

export interface CompanyDetails {
  id: string;
  company_name: string;
  raison_sociale: string | null;
  siret: string | null;
  siren: string | null;
  code_naf: string | null;
  naf_ape: string | null;
  legal_form: string | null;
  phone: string | null;
  email: string | null;
  website: string | null;
  urssaf_number: string | null;
  collective_agreement: string | null;
  idcc: string | null;
  effectif: number | null;
  paie_jour_de_fin: number | null;
  paie_occurrence: number | null;
  taux_at_mp: number | null;
  taux_vm: number | null;
  taux_fnal: number | null;
  adresse_rue: string | null;
  adresse_code_postal: string | null;
  adresse_ville: string | null;
  nom_signataire_rh: string | null;
  qualite_signataire_rh: string | null;
  service_sante_travail_nom: string | null;
  service_sante_travail_adresse_rue: string | null;
  service_sante_travail_adresse_code_postal: string | null;
  service_sante_travail_adresse_ville: string | null;
  service_sante_travail_telephone: string | null;
  service_sante_travail_email: string | null;
  settings?: {
    medical_follow_up_enabled?: boolean;
    public_holidays?: {
      observed_holiday_ids?: FrenchPublicHolidayId[];
    };
  };
  dsn_sync_mode?: DsnSyncMode | null;
}

export interface CompanyDetailsPayload {
  company_data: CompanyDetails;
  kpis: CompanyKPIs;
}

export interface CompanyOverviewAlertEmployee {
  id: string;
  first_name: string;
  last_name: string;
}

export type CompanyOverviewAlertAction =
  | "company_payroll_cc"
  | "company_payroll_jei"
  | "employee_list";

export interface CompanyOverviewAlert {
  code: string;
  severity: string;
  label: string;
  count?: number;
  action?: CompanyOverviewAlertAction;
  employee_ids?: string[];
  employees?: CompanyOverviewAlertEmployee[];
}

export interface CompanyOverview {
  demographics: {
    total_headcount: number;
    total_etp: number;
    average_tenure_years: number;
    average_age_years: number;
    cadre_percent: number;
    male_percent: number | null;
    female_percent: number | null;
  };
  movements: {
    new_hires_30_days: number;
    new_hires_90_days: number;
    new_hires_12_months: number;
    exits_30_days: number;
    exits_90_days: number;
    exits_12_months: number;
    turnover_rate_12_months: number;
  };
  absenteeism: {
    absenteeism_rate_percent: number;
    absence_days_last_30: number;
    top_absence_types: { type: string; count: number }[];
  };
  alerts: CompanyOverviewAlert[];
  dsn_coverage?: DsnCoverage | null;
  compliance: {
    at_mp_configured: boolean;
    vm_configured: boolean;
    collective_agreement_configured: boolean;
    cse_obligation: boolean;
    cse_ok: boolean;
    cse_status: string;
    carence_valid_until?: string | null;
    carence_expired?: boolean;
    jei_configured: boolean;
  };
  cdd_ending_within_30_days: number;
}

export type CompanyDetailsUpdate = Partial<
  Pick<
    CompanyDetails,
    | "company_name"
    | "raison_sociale"
    | "siret"
    | "siren"
    | "code_naf"
    | "naf_ape"
    | "legal_form"
    | "phone"
    | "email"
    | "website"
    | "urssaf_number"
    | "adresse_rue"
    | "adresse_code_postal"
    | "adresse_ville"
    | "nom_signataire_rh"
    | "qualite_signataire_rh"
    | "service_sante_travail_nom"
    | "service_sante_travail_adresse_rue"
    | "service_sante_travail_adresse_code_postal"
    | "service_sante_travail_adresse_ville"
    | "service_sante_travail_telephone"
    | "service_sante_travail_email"
    | "taux_at_mp"
    | "paie_jour_de_fin"
    | "paie_occurrence"
  >
> & {
  dsn_sync_mode?: DsnSyncMode;
};

export async function fetchCompanyDetails(): Promise<CompanyDetailsPayload> {
  const { data } = await apiClient.get<CompanyDetailsPayload>("/api/company/details");
  return data;
}

export async function fetchCompanyOverview(): Promise<CompanyOverview> {
  const { data } = await apiClient.get<CompanyOverview>("/api/company/overview");
  return data;
}

export async function patchCompanyDetails(
  body: CompanyDetailsUpdate,
): Promise<CompanyDetailsPayload> {
  const { data } = await apiClient.patch<CompanyDetailsPayload>("/api/company/details", body);
  return data;
}

export async function downloadCompanyExport(): Promise<void> {
  const response = await apiClient.get("/api/company/export", {
    responseType: "blob",
  });
  const blob = new Blob([response.data], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, "mon_entreprise.csv");
}

export interface CompanySettingsResponse {
  medical_follow_up_enabled: boolean;
  settings: Record<string, unknown>;
}

export interface PublicHolidaysSettingsUpdate {
  observed_holiday_ids: FrenchPublicHolidayId[];
}

export interface TrialPeriodBaremeLine {
  contract_type: string;
  statut: string;
  duree: number;
  unite: 'jours' | 'semaines' | 'mois';
  renouvellement: boolean;
}

export interface TrialPeriodSettingsUpdate {
  alerte_jours?: number;
  regle_legale_cdd?: boolean;
  exclusions?: string[];
  bareme?: TrialPeriodBaremeLine[];
}

export interface CompanySettingsUpdate {
  medical_follow_up_enabled?: boolean;
  public_holidays?: PublicHolidaysSettingsUpdate;
  periode_essai?: TrialPeriodSettingsUpdate;
}

export async function getCompanySettings(): Promise<CompanySettingsResponse> {
  const { data } = await apiClient.get<CompanySettingsResponse>('/api/company/settings');
  return data;
}

export async function patchCompanySettings(
  body: CompanySettingsUpdate
): Promise<CompanySettingsResponse> {
  const { data } = await apiClient.patch<CompanySettingsResponse>(
    '/api/company/settings',
    body
  );
  return data;
}
