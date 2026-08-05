import apiClient from '@/api/apiClient';

export type TrialPeriodUnit = 'jours' | 'semaines' | 'mois';
export type TrialPeriodStatus = 'en_cours' | 'confirmee' | 'rompue';

export interface TrialPeriod {
  id: string;
  company_id: string;
  employee_id: string;
  employee_name: string | null;
  start_date: string;
  duration_value: number;
  duration_unit: TrialPeriodUnit;
  renewal_allowed: boolean;
  renewed_at: string | null;
  renewal_duration_value: number | null;
  renewal_duration_unit: TrialPeriodUnit | null;
  end_date: string;
  status: TrialPeriodStatus;
  confirmed_at: string | null;
  hire_date: string | null;
  contract_type: string | null;
  statut: string | null;
}

export interface EmployeeToQualify {
  id: string;
  first_name: string;
  last_name: string;
  hire_date: string | null;
  contract_type: string | null;
  statut: string | null;
}

export interface TrialPeriodTracking {
  alert_days: number;
  en_cours: TrialPeriod[];
  a_confirmer: TrialPeriod[];
  a_qualifier: EmployeeToQualify[];
}

export interface ApplyBaremeResult {
  created: string[];
  skipped: { employee_id: string; raison: string }[];
}

export async function fetchTrialPeriodTracking(): Promise<TrialPeriodTracking> {
  const { data } = await apiClient.get<TrialPeriodTracking>('/api/trial-periods/tracking');
  return data;
}

export async function createTrialPeriod(body: {
  employee_id: string;
  start_date: string;
  duration_value: number;
  duration_unit: TrialPeriodUnit;
  renewal_allowed: boolean;
}): Promise<TrialPeriod> {
  const { data } = await apiClient.post<TrialPeriod>('/api/trial-periods', body);
  return data;
}

export async function updateTrialPeriod(
  id: string,
  body: {
    start_date?: string;
    duration_value?: number;
    duration_unit?: TrialPeriodUnit;
    renewal_allowed?: boolean;
  },
): Promise<TrialPeriod> {
  const { data } = await apiClient.patch<TrialPeriod>(`/api/trial-periods/${id}`, body);
  return data;
}

export async function confirmTrialPeriod(id: string): Promise<TrialPeriod> {
  const { data } = await apiClient.post<TrialPeriod>(`/api/trial-periods/${id}/confirm`);
  return data;
}

export async function renewTrialPeriod(
  id: string,
  body: { renewed_at: string; duration_value: number; duration_unit: TrialPeriodUnit },
): Promise<TrialPeriod> {
  const { data } = await apiClient.post<TrialPeriod>(`/api/trial-periods/${id}/renew`, body);
  return data;
}

export async function applyBareme(employeeIds: string[]): Promise<ApplyBaremeResult> {
  const { data } = await apiClient.post<ApplyBaremeResult>('/api/trial-periods/apply-bareme', {
    employee_ids: employeeIds,
  });
  return data;
}
