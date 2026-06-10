import apiClient from '@/api/apiClient';

export type LoanStatus =
  | 'draft'
  | 'active'
  | 'suspended'
  | 'repaid'
  | 'cancelled'
  | 'defaulted';

export interface EmployeeLoan {
  id: string;
  company_id: string;
  employee_id: string;
  principal_amount: number;
  annual_interest_rate: number;
  start_date: string;
  duration_months: number;
  monthly_payment: number;
  repayment_day: number;
  reason: string | null;
  status: LoanStatus;
  remaining_capital: number;
  requires_2062_declaration: boolean;
  declared_2062: boolean;
  contract_file_path: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  employee_name?: string | null;
}

export interface LoanInstallment {
  id?: string;
  loan_id?: string;
  installment_number: number;
  year: number;
  month: number;
  capital_part: number;
  interest_part: number;
  total_due: number;
  status: 'pending' | 'paid' | 'skipped';
  payslip_id?: string | null;
}

export interface LoanRepayment {
  id: string;
  loan_id: string;
  payslip_id: string | null;
  year: number;
  month: number;
  capital_amount: number;
  interest_amount: number;
  avantage_nature_amount: number;
  remaining_after: number;
  created_at: string | null;
}

export interface AmortizationPreviewLine {
  installment_number: number;
  year: number;
  month: number;
  capital_part: number;
  interest_part: number;
  total_due: number;
  remaining_capital: number;
}

export interface AmortizationPreview {
  monthly_payment: number;
  requires_2062_declaration: boolean;
  schedule: AmortizationPreviewLine[];
}

export interface EmployeeLoanCreate {
  employee_id: string;
  principal_amount: number;
  annual_interest_rate?: number;
  start_date: string;
  duration_months: number;
  repayment_day?: number;
  reason?: string;
  notes?: string;
  activate?: boolean;
}

export type EmployeeLoanUpdate = Partial<{
  status: LoanStatus;
  declared_2062: boolean;
  notes: string;
}>;

export const LOAN_STATUS_LABELS: Record<LoanStatus, string> = {
  draft: 'Brouillon',
  active: 'En cours',
  suspended: 'Suspendu',
  repaid: 'Soldé',
  cancelled: 'Annulé',
  defaulted: 'En défaut',
};

export const LOAN_STATUS_COLORS: Record<LoanStatus, string> = {
  draft: 'bg-gray-500',
  active: 'bg-blue-500',
  suspended: 'bg-yellow-500',
  repaid: 'bg-green-500',
  cancelled: 'bg-red-500',
  defaulted: 'bg-orange-500',
};

export async function getMyEmployeeLoans(): Promise<EmployeeLoan[]> {
  const { data } = await apiClient.get<EmployeeLoan[]>('/api/employee-loans/employees/me/loans');
  return data;
}

export async function activateEmployeeLoan(loanId: string): Promise<EmployeeLoan> {
  const { data } = await apiClient.post<EmployeeLoan>(
    `/api/employee-loans/${loanId}/activate`,
  );
  return data;
}

export async function markLoanDefaulted(loanId: string): Promise<EmployeeLoan> {
  const { data } = await apiClient.post<EmployeeLoan>(
    `/api/employee-loans/${loanId}/default`,
  );
  return data;
}

export async function recordEarlyRepayment(
  loanId: string,
  payload: { amount: number; repayment_date: string },
): Promise<EmployeeLoan> {
  const { data } = await apiClient.post<EmployeeLoan>(
    `/api/employee-loans/${loanId}/early-repayment`,
    payload,
  );
  return data;
}

export async function listEmployeeLoans(params?: {
  employee_id?: string;
  status?: LoanStatus;
}): Promise<EmployeeLoan[]> {
  const { data } = await apiClient.get<EmployeeLoan[]>('/api/employee-loans/', {
    params,
  });
  return data;
}

export async function getEmployeeLoans(employeeId: string): Promise<EmployeeLoan[]> {
  const { data } = await apiClient.get<EmployeeLoan[]>(
    `/api/employee-loans/employees/${employeeId}/loans`,
  );
  return data;
}

export async function getEmployeeLoan(loanId: string): Promise<EmployeeLoan> {
  const { data } = await apiClient.get<EmployeeLoan>(`/api/employee-loans/${loanId}`);
  return data;
}

export async function createEmployeeLoan(payload: EmployeeLoanCreate): Promise<EmployeeLoan> {
  const { data } = await apiClient.post<EmployeeLoan>('/api/employee-loans/', payload);
  return data;
}

export async function updateEmployeeLoan(
  loanId: string,
  payload: EmployeeLoanUpdate,
): Promise<EmployeeLoan> {
  const { data } = await apiClient.patch<EmployeeLoan>(
    `/api/employee-loans/${loanId}`,
    payload,
  );
  return data;
}

export async function cancelEmployeeLoan(loanId: string): Promise<EmployeeLoan> {
  const { data } = await apiClient.post<EmployeeLoan>(
    `/api/employee-loans/${loanId}/cancel`,
  );
  return data;
}

export async function deleteEmployeeLoan(loanId: string): Promise<void> {
  await apiClient.delete(`/api/employee-loans/${loanId}`);
}

export async function previewAmortization(payload: {
  principal_amount: number;
  annual_interest_rate?: number;
  start_date: string;
  duration_months: number;
}): Promise<AmortizationPreview> {
  const { data } = await apiClient.post<AmortizationPreview>(
    '/api/employee-loans/preview',
    payload,
  );
  return data;
}

export async function getLoanSchedule(loanId: string): Promise<LoanInstallment[]> {
  const { data } = await apiClient.get<LoanInstallment[]>(
    `/api/employee-loans/${loanId}/schedule`,
  );
  return data;
}

export async function getLoanRepayments(loanId: string): Promise<LoanRepayment[]> {
  const { data } = await apiClient.get<LoanRepayment[]>(
    `/api/employee-loans/${loanId}/repayments`,
  );
  return data;
}

export async function generateLoanContract(loanId: string): Promise<{ path: string }> {
  const { data } = await apiClient.post<{ path: string }>(
    `/api/employee-loans/${loanId}/contract`,
  );
  return data;
}

export async function getLoanContractUrl(loanId: string): Promise<{ url: string }> {
  const { data } = await apiClient.get<{ url: string }>(
    `/api/employee-loans/${loanId}/contract-url`,
  );
  return data;
}

export async function markLoanDeclared2062(loanId: string): Promise<EmployeeLoan> {
  const { data } = await apiClient.patch<EmployeeLoan>(
    `/api/employee-loans/${loanId}/declared-2062`,
  );
  return data;
}

export async function getEmployeeOutstandingLoans(employeeId: string): Promise<{
  employee_id: string;
  total_remaining_capital: number;
  active_loans_count: number;
  outstanding_loans_count: number;
  loans: EmployeeLoan[];
}> {
  const { data } = await apiClient.get(
    `/api/employee-loans/employees/${employeeId}/outstanding`,
  );
  return data;
}
