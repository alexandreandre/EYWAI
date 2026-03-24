// frontend/src/api/promotions.ts
// API pour la gestion des promotions et évolutions de carrière

import apiClient from "./apiClient";

// Types pour les statuts et types de promotion
export type PromotionStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "effective"
  | "cancelled";

export type PromotionType =
  | "poste"
  | "salaire"
  | "statut"
  | "classification"
  | "mixte";

export type RhAccessRole = "collaborateur_rh" | "rh" | "admin";

// Interface pour le salaire (JSONB)
export interface Salary {
  valeur: number;
  devise: string;
}

// Interface pour la classification (JSONB)
export interface Classification {
  coefficient?: number;
  classe_emploi?: number;
  groupe_emploi?: string;
}

// Interface complète d'une promotion
export interface Promotion {
  id: string;
  company_id: string;
  employee_id: string;
  promotion_type: PromotionType;
  previous_job_title: string | null;
  previous_salary: Salary | null;
  previous_statut: string | null;
  previous_classification: Classification | null;
  new_job_title: string | null;
  new_salary: Salary | null;
  new_statut: string | null;
  new_classification: Classification | null;
  previous_rh_access: string | null;
  new_rh_access: RhAccessRole | null;
  grant_rh_access: boolean;
  effective_date: string; // ISO date string
  request_date: string; // ISO date string
  status: PromotionStatus;
  reason: string | null;
  justification: string | null;
  performance_review_id: string | null;
  requested_by: string | null;
  approved_by: string | null;
  approved_at: string | null; // ISO datetime string
  rejection_reason: string | null;
  notes: Array<{
    author_id: string;
    timestamp: string;
    content: string;
    type?: string;
  }> | null;
  promotion_letter_url: string | null;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

// Interface pour un item de liste de promotion
export interface PromotionListItem {
  id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  promotion_type: PromotionType;
  new_job_title: string | null;
  new_salary: Salary | null;
  new_statut: string | null;
  effective_date: string; // ISO date string
  status: PromotionStatus;
  request_date: string; // ISO date string
  requested_by_name: string | null;
  approved_by_name: string | null;
  grant_rh_access: boolean;
  new_rh_access: RhAccessRole | null;
  performance_review_id: string | null;
  created_at: string; // ISO datetime string
}

// Interface pour la création d'une promotion
export interface PromotionCreate {
  employee_id: string;
  promotion_type: PromotionType;
  new_job_title?: string | null;
  new_salary?: Salary | null;
  new_statut?: string | null;
  new_classification?: Classification | null;
  effective_date: string; // ISO date string
  reason?: string | null;
  justification?: string | null;
  performance_review_id?: string | null;
  status?: "draft" | "pending_approval";
  grant_rh_access?: boolean;
  new_rh_access?: RhAccessRole | null;
}

// Interface pour la mise à jour d'une promotion
export interface PromotionUpdate {
  promotion_type?: PromotionType;
  new_job_title?: string | null;
  new_salary?: Salary | null;
  new_statut?: string | null;
  new_classification?: Classification | null;
  effective_date?: string | null; // ISO date string
  reason?: string | null;
  justification?: string | null;
  performance_review_id?: string | null;
  grant_rh_access?: boolean;
  new_rh_access?: RhAccessRole | null;
}

// Interface pour l'approbation d'une promotion
export interface PromotionApprove {
  notes?: string | null;
}

// Interface pour le rejet d'une promotion
export interface PromotionReject {
  rejection_reason: string;
}

// Interface pour l'accès RH d'un employé
export interface EmployeeRhAccess {
  has_access: boolean;
  current_role: string | null;
  can_grant_access: boolean;
  available_roles: RhAccessRole[];
}

// Interface pour les statistiques des promotions
export interface PromotionStats {
  total_promotions: number;
  promotions_by_month: Record<string, number>; // { "YYYY-MM": count }
  approval_rate: number; // Pourcentage (0-100)
  promotions_by_type: Record<string, number>;
  average_salary_increase: number | null; // Pourcentage moyen
  promotions_with_rh_access: number;
}

// Interface pour les paramètres de filtrage
export interface PromotionFilters {
  year?: number;
  status?: PromotionStatus;
  promotion_type?: PromotionType;
  employee_id?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

/**
 * Récupère la liste des promotions avec filtres optionnels
 */
export const getPromotions = (filters?: PromotionFilters) => {
  const searchParams = new URLSearchParams();
  
  if (filters?.year != null) {
    searchParams.set("year", String(filters.year));
  }
  if (filters?.status) {
    searchParams.set("status", filters.status);
  }
  if (filters?.promotion_type) {
    searchParams.set("promotion_type", filters.promotion_type);
  }
  if (filters?.employee_id) {
    searchParams.set("employee_id", filters.employee_id);
  }
  if (filters?.search) {
    searchParams.set("search", filters.search);
  }
  if (filters?.limit != null) {
    searchParams.set("limit", String(filters.limit));
  }
  if (filters?.offset != null) {
    searchParams.set("offset", String(filters.offset));
  }
  
  const qs = searchParams.toString();
  return apiClient.get<PromotionListItem[]>(
    `/api/promotions${qs ? `?${qs}` : ""}`
  );
};

/**
 * Récupère les détails d'une promotion spécifique
 */
export const getPromotion = (promotionId: string) => {
  return apiClient.get<Promotion>(`/api/promotions/${promotionId}`);
};

/**
 * Crée une nouvelle promotion
 */
export const createPromotion = (data: PromotionCreate) => {
  const payload = {
    ...data,
    new_job_title: data.new_job_title || null,
    new_salary: data.new_salary || null,
    new_statut: data.new_statut || null,
    new_classification: data.new_classification || null,
    reason: data.reason || null,
    justification: data.justification || null,
    performance_review_id: data.performance_review_id || null,
    status: data.status || "draft",
    grant_rh_access: data.grant_rh_access || false,
    new_rh_access: data.new_rh_access || null,
  };
  return apiClient.post<Promotion>("/api/promotions", payload);
};

/**
 * Met à jour une promotion existante
 */
export const updatePromotion = (
  promotionId: string,
  data: PromotionUpdate
) => {
  const payload: Record<string, unknown> = {};
  
  if (data.promotion_type !== undefined) {
    payload.promotion_type = data.promotion_type;
  }
  if (data.new_job_title !== undefined) {
    payload.new_job_title = data.new_job_title;
  }
  if (data.new_salary !== undefined) {
    payload.new_salary = data.new_salary;
  }
  if (data.new_statut !== undefined) {
    payload.new_statut = data.new_statut;
  }
  if (data.new_classification !== undefined) {
    payload.new_classification = data.new_classification;
  }
  if (data.effective_date !== undefined) {
    payload.effective_date = data.effective_date;
  }
  if (data.reason !== undefined) {
    payload.reason = data.reason;
  }
  if (data.justification !== undefined) {
    payload.justification = data.justification;
  }
  if (data.performance_review_id !== undefined) {
    payload.performance_review_id = data.performance_review_id;
  }
  if (data.grant_rh_access !== undefined) {
    payload.grant_rh_access = data.grant_rh_access;
  }
  if (data.new_rh_access !== undefined) {
    payload.new_rh_access = data.new_rh_access;
  }
  
  return apiClient.put<Promotion>(`/api/promotions/${promotionId}`, payload);
};

/**
 * Soumet une promotion pour approbation (passe de draft à pending_approval)
 */
export const submitPromotion = (promotionId: string) => {
  return apiClient.post<Promotion>(
    `/api/promotions/${promotionId}/submit`
  );
};

/**
 * Approuve une promotion
 */
export const approvePromotion = (
  promotionId: string,
  data?: PromotionApprove
) => {
  const payload = data || {};
  return apiClient.post<Promotion>(
    `/api/promotions/${promotionId}/approve`,
    payload
  );
};

/**
 * Rejette une promotion
 */
export const rejectPromotion = (
  promotionId: string,
  data: PromotionReject
) => {
  return apiClient.post<Promotion>(
    `/api/promotions/${promotionId}/reject`,
    data
  );
};

/**
 * Marque une promotion comme effective (applique les changements)
 */
export const markPromotionEffective = (promotionId: string) => {
  return apiClient.post<Promotion>(
    `/api/promotions/${promotionId}/mark-effective`
  );
};

/**
 * Supprime une promotion (uniquement si statut = draft)
 */
export const deletePromotion = (promotionId: string) => {
  return apiClient.delete(`/api/promotions/${promotionId}`);
};

/**
 * Récupère l'URL signée du document PDF de promotion
 */
export const downloadPromotionDocument = async (promotionId: string) => {
  const response = await apiClient.get<{ url: string }>(
    `/api/promotions/${promotionId}/document`
  );
  return response.data.url;
};

/**
 * Récupère toutes les promotions d'un employé spécifique
 */
export const getEmployeePromotions = (employeeId: string) => {
  return apiClient.get<PromotionListItem[]>(
    `/api/employees/${employeeId}/promotions`
  );
};

/**
 * Récupère les informations d'accès RH d'un employé
 */
export const getEmployeeRhAccess = (employeeId: string) => {
  return apiClient.get<EmployeeRhAccess>(
    `/api/employees/${employeeId}/rh-access`
  );
};

/**
 * Récupère les statistiques des promotions
 */
export const getPromotionStats = (year?: number) => {
  const searchParams = new URLSearchParams();
  if (year != null) {
    searchParams.set("year", String(year));
  }
  const qs = searchParams.toString();
  return apiClient.get<PromotionStats>(
    `/api/promotions/stats${qs ? `?${qs}` : ""}`
  );
};
