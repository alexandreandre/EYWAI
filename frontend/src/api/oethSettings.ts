import apiClient from '@/api/apiClient';

export interface OethSettings {
  id: string | null;
  company_id: string;
  oeth_assujetti_override: boolean | null;
  oeth_assujetti: boolean;
  date_franchissement_seuil_20: string | null;
  neutralisation_active: boolean;
  accord_agree_code: string | null;
  accord_agree_valid_from: string | null;
  accord_agree_valid_to: string | null;
  declaring_establishment_siret: string | null;
  departement: string | null;
  taux_obligation: number;
  effectif_actif: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export type OethSettingsUpdate = Partial<
  Omit<
    OethSettings,
    | 'id'
    | 'company_id'
    | 'oeth_assujetti'
    | 'neutralisation_active'
    | 'effectif_actif'
    | 'created_at'
    | 'updated_at'
  >
>;

export interface EmployeeBoethProfile {
  id: string | null;
  employee_id: string;
  company_id: string;
  boeth_code: string;
  boeth_label: string | null;
  valid_from: string;
  valid_to: string | null;
  document_type: string | null;
  document_expires_at: string | null;
  notes: string | null;
  is_active: boolean;
}

export interface EmployeeBoethUpdate {
  boeth_code: string;
  valid_from: string;
  valid_to?: string | null;
  document_type?: string | null;
  document_expires_at?: string | null;
  notes?: string | null;
}

export interface OethCompliance {
  effectif_actif: number;
  boeth_count: number;
  taux_emploi_pct: number;
  quota_6_pct: number;
  boeth_manquants: number;
  oeth_assujetti: boolean;
  neutralisation_active: boolean;
  accord_agree_active: boolean;
  alertes: string[];
}

export interface BoethExterne {
  id?: string | null;
  external_type: string;
  external_label?: string | null;
  annual_average_count: number;
  contract_reference?: string | null;
  amount_ht: number;
}

export interface OethDeduction {
  id?: string | null;
  deduction_type: string;
  deduction_label?: string | null;
  amount_eur: number;
  provider_name?: string | null;
  reference?: string | null;
}

export interface OethEcapPosition {
  id?: string | null;
  job_code_pcs_ese: string;
  annual_average_count: number;
}

export interface OethAnnualReview {
  id: string | null;
  company_id: string;
  employment_year: number;
  ema_assujettissement: number | null;
  ema_boeth_interne: number | null;
  ema_boeth_externe: number | null;
  ema_ecap: number | null;
  urssaf_ema_assujettissement: number | null;
  urssaf_ema_boeth: number | null;
  urssaf_ema_ecap: number | null;
  urssaf_notified_at: string | null;
  boeth_manquants: number | null;
  contribution_brute: number | null;
  contribution_nette: number | null;
  contribution_due: number | null;
  deductions_detail: Record<string, number>;
  neutralisation_active: boolean;
  surcontribution_applicable: boolean;
  accord_agree_active: boolean;
  status: string;
  declared_in_dsn_period: string | null;
  taux_emploi_pct: number | null;
  quota_boeth: number | null;
  externes: BoethExterne[];
  deductions: OethDeduction[];
  ecap_positions: OethEcapPosition[];
}

export const BOETH_CODE_OPTIONS = [
  { value: '01', label: 'RQTH — Travailleur reconnu handicapé' },
  { value: '02', label: 'Victime AT/MP (incapacité ≥ 10 %)' },
  { value: '03', label: 'Pension invalidité (≥ 2/3)' },
  { value: '04', label: 'Pension militaire invalidité (L.241-2)' },
  { value: '05', label: 'Pension militaire invalidité (L.241-3/4)' },
  { value: '06', label: 'Allocation/rente invalidité sapeurs-pompiers' },
  { value: '07', label: 'Carte mobilité inclusion — invalidité' },
  { value: '08', label: 'Titulaire AAH' },
  { value: '09', label: 'Pension militaire invalidité (L.241-5/6)' },
  { value: '11', label: 'Agent public — ATI' },
  { value: '12', label: 'Stage PCH/ACTP/AEEH' },
] as const;

export async function getOethSettings(): Promise<OethSettings> {
  const response = await apiClient.get<OethSettings>('/api/oeth-settings/');
  return response.data;
}

export async function saveOethSettings(data: OethSettingsUpdate): Promise<OethSettings> {
  const response = await apiClient.put<OethSettings>('/api/oeth-settings/', data);
  return response.data;
}

export async function getOethCompliance(): Promise<OethCompliance> {
  const response = await apiClient.get<OethCompliance>('/api/oeth-settings/compliance');
  return response.data;
}

export async function getEmployeeBoeth(employeeId: string): Promise<EmployeeBoethProfile | null> {
  const response = await apiClient.get<EmployeeBoethProfile | null>(
    `/api/oeth-settings/employees/${employeeId}/boeth`,
  );
  return response.data;
}

export async function saveEmployeeBoeth(
  employeeId: string,
  data: EmployeeBoethUpdate,
): Promise<EmployeeBoethProfile> {
  const response = await apiClient.put<EmployeeBoethProfile>(
    `/api/oeth-settings/employees/${employeeId}/boeth`,
    data,
  );
  return response.data;
}

export async function deleteEmployeeBoeth(employeeId: string): Promise<void> {
  await apiClient.delete(`/api/oeth-settings/employees/${employeeId}/boeth`);
}

export async function getOethAnnualReview(year: number): Promise<OethAnnualReview> {
  const response = await apiClient.get<OethAnnualReview>(
    `/api/oeth-settings/annual-reviews/${year}`,
  );
  return response.data;
}

export async function computeOethAnnualReview(year: number): Promise<OethAnnualReview> {
  const response = await apiClient.post<OethAnnualReview>(
    `/api/oeth-settings/annual-reviews/${year}/compute`,
  );
  return response.data;
}

export async function saveOethExternes(
  year: number,
  items: BoethExterne[],
): Promise<OethAnnualReview> {
  const response = await apiClient.put<OethAnnualReview>(
    `/api/oeth-settings/annual-reviews/${year}/externes`,
    { items },
  );
  return response.data;
}

export async function saveOethDeductions(
  year: number,
  items: OethDeduction[],
): Promise<OethAnnualReview> {
  const response = await apiClient.put<OethAnnualReview>(
    `/api/oeth-settings/annual-reviews/${year}/deductions`,
    { items },
  );
  return response.data;
}

export async function saveOethEcapPositions(
  year: number,
  items: OethEcapPosition[],
): Promise<OethAnnualReview> {
  const response = await apiClient.put<OethAnnualReview>(
    `/api/oeth-settings/annual-reviews/${year}/ecap`,
    { items },
  );
  return response.data;
}

export const OETH_EXTERNAL_TYPE_OPTIONS = [
  { value: '01', label: '01 — Sous-traitance / entreprise adaptée' },
  { value: '02', label: '02 — Prestation ESAT / EA' },
  { value: '03', label: '03 — Mise à disposition groupe' },
  { value: '04', label: '04 — Autre BOETH externe' },
] as const;

export const OETH_DEDUCTION_TYPE_OPTIONS = [
  { value: '060', label: '060 — Déduction ECAP' },
  { value: '061', label: '061 — Dépenses handicap (61)' },
  { value: '062', label: '062 — Dépenses handicap (62)' },
  { value: '063', label: '063 — Dépenses handicap (63)' },
  { value: '064', label: '064 — Dépenses handicap (64)' },
] as const;

export async function saveUrssafOverride(
  year: number,
  data: {
    urssaf_ema_assujettissement?: number | null;
    urssaf_ema_boeth?: number | null;
    urssaf_ema_ecap?: number | null;
    urssaf_notified_at?: string | null;
  },
): Promise<OethAnnualReview> {
  const response = await apiClient.put<OethAnnualReview>(
    `/api/oeth-settings/annual-reviews/${year}/urssaf-override`,
    data,
  );
  return response.data;
}
