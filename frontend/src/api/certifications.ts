import apiClient from "./apiClient";

export type ComputedStatus = "valid" | "expiring_soon" | "expired" | "no_expiry";

export type CertificationRef = {
  id: string;
  company_id: string;
  name: string;
  code?: string | null;
  category: string;
  validity_months?: number | null;
  alert_days: number;
  certifying_body?: string | null;
  description?: string | null;
  legal_link?: string | null;
  status: string;
  created_at?: string | null;
};

export type EmployeeCertification = {
  id: string;
  company_id: string;
  employee_id: string;
  certification_id: string;
  obtained_date: string;
  expiry_date?: string | null;
  certifying_body?: string | null;
  certificate_number?: string | null;
  certificate_url?: string | null;
  notes?: string | null;
  is_archived: boolean;
  created_at?: string | null;
  computed_status: ComputedStatus;
  certification_ref?: CertificationRef | null;
  employee_name?: string | null;
};

export type CertificationRefCreate = {
  name: string;
  code?: string | null;
  category: string;
  validity_months?: number | null;
  alert_days?: number;
  certifying_body?: string | null;
  description?: string | null;
  legal_link?: string | null;
};

export type CertificationRefUpdate = Partial<CertificationRefCreate> & {
  status?: string | null;
};

export type EmployeeCertificationCreate = {
  employee_id: string;
  certification_id: string;
  obtained_date: string;
  expiry_date?: string | null;
  certifying_body?: string | null;
  certificate_number?: string | null;
  notes?: string | null;
};

export type EmployeeCertificationUpdate = {
  certification_id?: string;
  obtained_date?: string;
  expiry_date?: string | null;
  certifying_body?: string | null;
  certificate_number?: string | null;
  certificate_url?: string | null;
  notes?: string | null;
  is_archived?: boolean;
};

export type DashboardCounts = { expiring: number; expired: number };

export async function getCertificationRefs(): Promise<CertificationRef[]> {
  const res = await apiClient.get<CertificationRef[]>("/api/certifications/refs");
  return res.data ?? [];
}

export async function getCertificationRef(id: string): Promise<CertificationRef> {
  const res = await apiClient.get<CertificationRef>(`/api/certifications/refs/${id}`);
  return res.data;
}

export async function createCertificationRef(
  body: CertificationRefCreate,
): Promise<CertificationRef> {
  const res = await apiClient.post<CertificationRef>("/api/certifications/refs", body);
  return res.data;
}

export async function updateCertificationRef(
  id: string,
  body: CertificationRefUpdate,
): Promise<CertificationRef> {
  const res = await apiClient.put<CertificationRef>(`/api/certifications/refs/${id}`, body);
  return res.data;
}

export async function archiveCertificationRef(id: string): Promise<void> {
  await apiClient.post(`/api/certifications/refs/${id}/archive`);
}

export async function getEmployeeCertifications(params?: {
  employee_id?: string;
  include_archived?: boolean;
}): Promise<EmployeeCertification[]> {
  const search = new URLSearchParams();
  if (params?.employee_id) search.set("employee_id", params.employee_id);
  if (params?.include_archived) search.set("include_archived", "true");
  const q = search.toString();
  const res = await apiClient.get<EmployeeCertification[]>(
    `/api/certifications${q ? `?${q}` : ""}`,
  );
  return res.data ?? [];
}

export async function getEmployeeCertification(id: string): Promise<EmployeeCertification> {
  const res = await apiClient.get<EmployeeCertification>(`/api/certifications/${id}`);
  return res.data;
}

export async function createEmployeeCertification(
  body: EmployeeCertificationCreate,
): Promise<EmployeeCertification> {
  const res = await apiClient.post<EmployeeCertification>("/api/certifications", body);
  return res.data;
}

export async function updateEmployeeCertification(
  id: string,
  body: EmployeeCertificationUpdate,
): Promise<EmployeeCertification> {
  const res = await apiClient.put<EmployeeCertification>(`/api/certifications/${id}`, body);
  return res.data;
}

export async function archiveEmployeeCertification(id: string): Promise<void> {
  await apiClient.post(`/api/certifications/${id}/archive`);
}

export async function uploadCertificateFile(
  certId: string,
  file: File,
): Promise<EmployeeCertification> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiClient.post<EmployeeCertification>(
    `/api/certifications/${certId}/upload-certificate`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } },
  );
  return res.data;
}

export async function getDashboardCounts(): Promise<DashboardCounts> {
  const res = await apiClient.get<DashboardCounts>("/api/certifications/dashboard-counts");
  return res.data;
}
