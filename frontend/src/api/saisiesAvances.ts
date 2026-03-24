// frontend/src/api/saisiesAvances.ts

import apiClient from './apiClient';

// =====================================================================
// TYPES
// =====================================================================

export type SalarySeizureType = 'saisie_arret' | 'pension_alimentaire' | 'atd' | 'satd';
export type SalarySeizureStatus = 'active' | 'suspended' | 'closed';
export type CalculationMode = 'fixe' | 'pourcentage' | 'barème_legal';
export type SalaryAdvanceStatus = 'pending' | 'approved' | 'rejected' | 'paid';
export type RepaymentMode = 'single' | 'multiple';
export type PaymentMethod = 'virement' | 'cheque' | 'especes';

type EmployeeLite = {
  id: string;
  first_name: string;
  last_name: string;
};

export interface SalarySeizure {
  id: string;
  company_id: string;
  employee_id: string;
  type: SalarySeizureType;
  reference_legale?: string;
  creditor_name: string;
  creditor_iban?: string;
  amount?: number;
  calculation_mode: CalculationMode;
  percentage?: number;
  start_date: string;
  end_date?: string;
  status: SalarySeizureStatus;
  priority: number;
  document_url?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  created_by?: string;
}

export interface SalarySeizureCreate {
  employee_id: string;
  type: SalarySeizureType;
  reference_legale?: string;
  creditor_name: string;
  creditor_iban?: string;
  amount?: number;
  calculation_mode?: CalculationMode;
  percentage?: number;
  start_date: string;
  end_date?: string;
  priority?: number;
  document_url?: string;
  notes?: string;
}

export interface SalarySeizureUpdate {
  status?: SalarySeizureStatus;
  amount?: number;
  calculation_mode?: CalculationMode;
  percentage?: number;
  end_date?: string;
  notes?: string;
}

export interface SalaryAdvance {
  id: string;
  company_id: string;
  employee_id: string;
  employee_name?: string; // Nom complet de l'employé (prénom + nom)
  requested_amount: number;
  approved_amount?: number;
  requested_date: string;
  payment_date?: string;
  payment_method?: PaymentMethod;
  status: SalaryAdvanceStatus;
  repayment_mode: RepaymentMode;
  repayment_months: number;
  remaining_amount: number;
  remaining_to_pay?: number; // Montant restant à verser (basé sur les paiements réels)
  request_comment?: string;
  rejection_reason?: string;
  created_at: string;
  updated_at: string;
  approved_by?: string;
  approved_at?: string;
}

export interface SalaryAdvanceCreate {
  employee_id: string;
  requested_amount: number;
  requested_date: string;
  repayment_mode?: RepaymentMode;
  repayment_months?: number;
  request_comment?: string;
}

export interface SalaryAdvanceApprove {
  approved_amount?: number;
  payment_method?: PaymentMethod;
  repayment_mode?: RepaymentMode;
  repayment_months?: number;
}

export interface SalaryAdvanceReject {
  rejection_reason: string;
}

export interface SeizableAmountCalculation {
  net_salary: number;
  dependents_count: number;
  adjusted_salary: number;
  seizable_amount: number;
  minimum_untouchable: number;
}

export interface AdvanceAvailableAmount {
  daily_salary: number;
  days_worked: number;
  outstanding_advances: number;
  available_amount: number;
  max_advance_days: number;
}

export interface SalarySeizureDeduction {
  id: string;
  seizure_id: string;
  payslip_id: string;
  year: number;
  month: number;
  gross_salary: number;
  net_salary: number;
  seizable_amount: number;
  deducted_amount: number;
  created_at: string;
}

export interface SalaryAdvanceRepayment {
  id: string;
  advance_id: string;
  payslip_id: string;
  year: number;
  month: number;
  repayment_amount: number;
  remaining_after: number;
  created_at: string;
}

// =====================================================================
// API FUNCTIONS - SAISIES
// =====================================================================

export async function createSalarySeizure(data: SalarySeizureCreate): Promise<SalarySeizure> {
  const response = await apiClient.post('/api/saisies-avances/salary-seizures', data);
  return response.data;
}

export async function getSalarySeizures(params?: {
  employee_id?: string;
  status?: SalarySeizureStatus;
}): Promise<SalarySeizure[]> {
  const response = await apiClient.get('/api/saisies-avances/salary-seizures', { params });
  return response.data;
}

export async function getSalarySeizure(id: string): Promise<SalarySeizure> {
  const response = await apiClient.get(`/api/saisies-avances/salary-seizures/${id}`);
  return response.data;
}

export async function updateSalarySeizure(
  id: string,
  data: SalarySeizureUpdate
): Promise<SalarySeizure> {
  const response = await apiClient.patch(`/api/saisies-avances/salary-seizures/${id}`, data);
  return response.data;
}

export async function deleteSalarySeizure(id: string): Promise<void> {
  await apiClient.delete(`/api/saisies-avances/salary-seizures/${id}`);
}

export async function calculateSeizableAmount(
  net_salary: number,
  dependents_count: number = 0
): Promise<SeizableAmountCalculation> {
  const response = await apiClient.post('/api/saisies-avances/salary-seizures/calculate-seizable', {
    net_salary,
    dependents_count
  });
  return response.data;
}

export async function getEmployeeSalarySeizures(employee_id: string): Promise<SalarySeizure[]> {
  const response = await apiClient.get(`/api/saisies-avances/employees/${employee_id}/salary-seizures`);
  return response.data;
}

// =====================================================================
// API FUNCTIONS - AVANCES
// =====================================================================

export async function createSalaryAdvance(data: SalaryAdvanceCreate): Promise<SalaryAdvance> {
  const response = await apiClient.post('/api/saisies-avances/salary-advances', data);
  return response.data;
}

async function getEmployeesLite(): Promise<EmployeeLite[]> {
  // IMPORTANT: adapte l'URL à TON endpoint réel qui liste les employés
  // Exemples possibles chez toi : '/api/employees', '/api/company/employees', etc.
  const response = await apiClient.get('/api/employees');
  return response.data;
}

export async function getSalaryAdvances(params?: {
  employee_id?: string;
  status?: SalaryAdvanceStatus;
}): Promise<SalaryAdvance[]> {
  const [advancesRes, employees] = await Promise.all([
    apiClient.get('/api/saisies-avances/salary-advances', { params }),
    getEmployeesLite(),
  ]);

  const employeesById = new Map(
    (employees ?? []).map((e) => [e.id, `${e.first_name} ${e.last_name}`] as const)
  );

  const advances: SalaryAdvance[] = advancesRes.data ?? [];

  return advances.map((a) => ({
    ...a,
    employee_name: a.employee_name ?? employeesById.get(a.employee_id) ?? undefined,
  }));
}

export async function getSalaryAdvance(id: string): Promise<SalaryAdvance> {
  const response = await apiClient.get(`/api/saisies-avances/salary-advances/${id}`);
  return response.data;
}

export async function approveSalaryAdvance(
  id: string
): Promise<SalaryAdvance> {
  const response = await apiClient.patch(`/api/saisies-avances/salary-advances/${id}/approve`);
  return response.data;
}

export async function rejectSalaryAdvance(
  id: string,
  data: SalaryAdvanceReject
): Promise<SalaryAdvance> {
  const response = await apiClient.patch(`/api/saisies-avances/salary-advances/${id}/reject`, data);
  return response.data;
}

export async function getEmployeeSalaryAdvances(employee_id: string): Promise<SalaryAdvance[]> {
  const response = await apiClient.get(`/api/saisies-avances/employees/${employee_id}/salary-advances`);
  return response.data;
}

export async function getMySalaryAdvances(): Promise<SalaryAdvance[]> {
  const response = await apiClient.get('/api/saisies-avances/employees/me/salary-advances');
  return response.data;
}

export async function getMyAdvanceAvailable(): Promise<AdvanceAvailableAmount> {
  const response = await apiClient.get('/api/saisies-avances/employees/me/advance-available');
  return response.data;
}

// =====================================================================
// API FUNCTIONS - INTÉGRATION BULLETINS
// =====================================================================

export async function getPayslipDeductions(payslip_id: string): Promise<SalarySeizureDeduction[]> {
  const response = await apiClient.get(`/api/saisies-avances/payslips/${payslip_id}/deductions`);
  return response.data;
}

export async function getPayslipAdvanceRepayments(
  payslip_id: string
): Promise<SalaryAdvanceRepayment[]> {
  const response = await apiClient.get(`/api/saisies-avances/payslips/${payslip_id}/advance-repayments`);
  return response.data;
}

// =====================================================================
// API FUNCTIONS - PAIEMENTS D'AVANCES
// =====================================================================

export interface SalaryAdvancePayment {
  id: string;
  advance_id: string;
  company_id: string;
  payment_amount: number;
  payment_date: string;
  payment_method?: 'virement' | 'cheque' | 'especes';
  proof_file_path?: string;
  proof_file_name?: string;
  proof_file_type?: string;
  notes?: string;
  created_at: string;
  created_by?: string;
}

export interface SalaryAdvancePaymentCreate {
  advance_id: string;
  payment_amount: number;
  payment_date: string;
  payment_method?: 'virement' | 'cheque' | 'especes';
  proof_file_path?: string;
  proof_file_name?: string;
  proof_file_type?: string;
  notes?: string;
}

export interface SignedUploadURL {
  path: string;
  signedURL: string;
}

export async function getPaymentUploadUrl(filename: string): Promise<SignedUploadURL> {
  const response = await apiClient.post('/api/saisies-avances/advance-payments/upload-url', { filename });
  return response.data;
}

export async function uploadPaymentFile(signedURL: string, file: File): Promise<void> {
  const secureUrl = signedURL.replace(/^http:\/\//i, 'https://');
  const response = await fetch(secureUrl, {
    method: 'PUT',
    headers: {
      'Content-Type': file.type,
    },
    body: file,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(`Échec de l'upload vers Supabase Storage. Statut: ${response.status}`);
  }
}

export async function createAdvancePayment(data: SalaryAdvancePaymentCreate): Promise<SalaryAdvancePayment> {
  const response = await apiClient.post('/api/saisies-avances/advance-payments', data);
  return response.data;
}

export async function getAdvancePayments(advance_id: string): Promise<SalaryAdvancePayment[]> {
  const response = await apiClient.get(`/api/saisies-avances/advances/${advance_id}/payments`);
  return response.data;
}

export async function getPaymentProofUrl(payment_id: string): Promise<{ url: string }> {
  const response = await apiClient.get(`/api/saisies-avances/advance-payments/${payment_id}/proof-url`);
  return response.data;
}

export async function deleteAdvancePayment(payment_id: string): Promise<void> {
  await apiClient.delete(`/api/saisies-avances/advance-payments/${payment_id}`);
}
