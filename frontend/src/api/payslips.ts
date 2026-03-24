// frontend/src/api/payslips.ts

import apiClient from './apiClient';

// =====================================================
// TYPES
// =====================================================

export interface InternalNote {
  id: string;
  author_id: string;
  author_name: string;
  timestamp: string;
  content: string;
}

export interface HistoryEntry {
  version: number;
  edited_at: string;
  edited_by: string;
  edited_by_name: string;
  changes_summary: string;
  previous_payslip_data: any;
  previous_pdf_url?: string;
}

export interface PayslipInfo {
  id: string;
  name: string;
  month: number;
  year: number;
  url: string;
  net_a_payer?: number;
  manually_edited: boolean;
  edit_count: number;
  edited_at?: string;
  edited_by?: string;
}

export interface PayslipDetail {
  id: string;
  employee_id: string;
  company_id: string;
  name: string;
  month: number;
  year: number;
  url: string;
  pdf_storage_path: string;
  payslip_data: any;
  manually_edited: boolean;
  edit_count: number;
  edited_at?: string;
  edited_by?: string;
  internal_notes: InternalNote[];
  pdf_notes?: string;
  edit_history: HistoryEntry[];
  cumuls?: any;
}

export interface PayslipEditRequest {
  payslip_data: any;
  changes_summary: string;
  pdf_notes?: string;
  internal_note?: string;
}

export interface PayslipEditResponse {
  status: string;
  message: string;
  payslip: PayslipDetail;
  new_pdf_url: string;
}

export interface PayslipRestoreRequest {
  version: number;
}

export interface PayslipRestoreResponse {
  status: string;
  message: string;
  payslip: PayslipDetail;
  restored_version: number;
}

// =====================================================
// API FUNCTIONS
// =====================================================

/**
 * Récupère les détails complets d'un bulletin de paie
 */
export const getPayslipDetails = async (payslipId: string): Promise<PayslipDetail> => {
  const response = await apiClient.get<PayslipDetail>(`/api/payslips/${payslipId}`);
  return response.data;
};

/**
 * Modifie un bulletin de paie
 */
export const editPayslip = async (
  payslipId: string,
  editRequest: PayslipEditRequest
): Promise<PayslipEditResponse> => {
  const response = await apiClient.post<PayslipEditResponse>(
    `/api/payslips/${payslipId}/edit`,
    editRequest
  );
  return response.data;
};

/**
 * Récupère l'historique des modifications d'un bulletin
 */
export const getPayslipHistory = async (payslipId: string): Promise<HistoryEntry[]> => {
  const response = await apiClient.get<HistoryEntry[]>(`/api/payslips/${payslipId}/history`);
  return response.data;
};

/**
 * Restaure une version précédente d'un bulletin
 */
export const restorePayslipVersion = async (
  payslipId: string,
  version: number
): Promise<PayslipRestoreResponse> => {
  const response = await apiClient.post<PayslipRestoreResponse>(
    `/api/payslips/${payslipId}/restore`,
    { version }
  );
  return response.data;
};

/**
 * Récupère la liste des bulletins de l'utilisateur connecté
 */
export const getMyPayslips = async (): Promise<PayslipInfo[]> => {
  const response = await apiClient.get<PayslipInfo[]>('/api/me/payslips');
  return response.data;
};

/**
 * Récupère la liste des bulletins d'un employé
 */
export const getEmployeePayslips = async (employeeId: string): Promise<PayslipInfo[]> => {
  const response = await apiClient.get<PayslipInfo[]>(`/api/employees/${employeeId}/payslips`);
  return response.data;
};

/**
 * Supprime un bulletin de paie
 */
export const deletePayslip = async (payslipId: string): Promise<void> => {
  await apiClient.delete(`/api/payslips/${payslipId}`);
};

/**
 * Génère un nouveau bulletin de paie
 */
export const generatePayslip = async (data: {
  employee_id: string;
  year: number;
  month: number;
}): Promise<{ status: string; message: string; download_url: string }> => {
  const response = await apiClient.post('/api/actions/generate-payslip', data);
  return response.data;
};
