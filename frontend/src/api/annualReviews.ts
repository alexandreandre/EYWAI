// frontend/src/api/annualReviews.ts
// API pour le suivi des entretiens

import apiClient from "./apiClient";

export type AnnualReviewStatus =
  | "planifie"
  | "en_attente_acceptation"
  | "accepte"
  | "refuse"
  | "realise"
  | "cloture";

export interface AnnualReview {
  id: string;
  employee_id: string;
  company_id: string;
  year: number;
  status: AnnualReviewStatus;
  planned_date: string | null;
  completed_date: string | null;
  employee_preparation_notes: string | null;
  employee_preparation_validated_at: string | null;
  rh_preparation_template?: string | null; // Notes RH pour l'entretien
  employee_acceptance_status?: "accepte" | "refuse" | null;
  employee_acceptance_date?: string | null;
  meeting_report?: string | null; // Compte-rendu d'entretien
  // Champs RH pour la fiche complète
  rh_notes?: string | null;
  evaluation_summary?: string | null;
  objectives_achieved?: string | null;
  objectives_next_year?: string | null;
  strengths?: string | null;
  improvement_areas?: string | null;
  training_needs?: string | null;
  career_development?: string | null;
  salary_review?: string | null;
  overall_rating?: string | null;
  next_review_date?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AnnualReviewListItem {
  id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  year: number;
  status: AnnualReviewStatus;
  planned_date: string | null;
  completed_date: string | null;
  created_at: string | null;
}

export interface AnnualReviewCreate {
  employee_id: string;
  year: number;
  status?: AnnualReviewStatus;
  planned_date?: string | null;
  rh_preparation_template?: string | null; // Notes RH pour l'entretien
}

export interface AnnualReviewUpdate {
  planned_date?: string | null;
  completed_date?: string | null;
  status?: AnnualReviewStatus;
  employee_preparation_notes?: string | null;
  rh_preparation_template?: string | null; // Notes RH
  employee_acceptance_status?: "accepte" | "refuse" | null;
  meeting_report?: string | null; // Compte-rendu d'entretien
  // Champs RH pour la fiche complète
  rh_notes?: string | null;
  evaluation_summary?: string | null;
  objectives_achieved?: string | null;
  objectives_next_year?: string | null;
  strengths?: string | null;
  improvement_areas?: string | null;
  training_needs?: string | null;
  career_development?: string | null;
  salary_review?: string | null;
  overall_rating?: string | null;
  next_review_date?: string | null;
}

export const getEmployeeAnnualReviews = (employeeId: string) => {
  return apiClient.get<AnnualReview[]>(
    `/api/annual-reviews/by-employee/${employeeId}`
  );
};

export const getAnnualReview = (reviewId: string) => {
  return apiClient.get<AnnualReview>(`/api/annual-reviews/${reviewId}`);
};

export const getAllAnnualReviews = (params?: {
  year?: number;
  status?: string;
}) => {
  const searchParams = new URLSearchParams();
  if (params?.year != null) searchParams.set("year", String(params.year));
  if (params?.status != null) searchParams.set("status", params.status);
  const qs = searchParams.toString();
  return apiClient.get<AnnualReviewListItem[]>(
    `/api/annual-reviews${qs ? `?${qs}` : ""}`
  );
};

export const getMyAnnualReviews = () => {
  return apiClient.get<AnnualReview[]>("/api/annual-reviews/me");
};

export const getMyCurrentAnnualReview = () => {
  return apiClient.get<AnnualReview | null>("/api/annual-reviews/me/current");
};

export const createAnnualReview = (data: AnnualReviewCreate) => {
  const payload = {
    ...data,
    planned_date: data.planned_date || null,
  };
  return apiClient.post<AnnualReview>("/api/annual-reviews", payload);
};

export const updateAnnualReview = (
  reviewId: string,
  data: AnnualReviewUpdate
) => {
  const payload: Record<string, unknown> = {};
  if (data.planned_date !== undefined) payload.planned_date = data.planned_date;
  if (data.completed_date !== undefined)
    payload.completed_date = data.completed_date;
  if (data.status !== undefined) payload.status = data.status;
  if (data.employee_preparation_notes !== undefined)
    payload.employee_preparation_notes = data.employee_preparation_notes;
  if (data.rh_preparation_template !== undefined) payload.rh_preparation_template = data.rh_preparation_template;
  if (data.employee_acceptance_status !== undefined) payload.employee_acceptance_status = data.employee_acceptance_status;
  if (data.meeting_report !== undefined) payload.meeting_report = data.meeting_report;
  // Champs RH
  if (data.rh_notes !== undefined) payload.rh_notes = data.rh_notes;
  if (data.evaluation_summary !== undefined) payload.evaluation_summary = data.evaluation_summary;
  if (data.objectives_achieved !== undefined) payload.objectives_achieved = data.objectives_achieved;
  if (data.objectives_next_year !== undefined) payload.objectives_next_year = data.objectives_next_year;
  if (data.strengths !== undefined) payload.strengths = data.strengths;
  if (data.improvement_areas !== undefined) payload.improvement_areas = data.improvement_areas;
  if (data.training_needs !== undefined) payload.training_needs = data.training_needs;
  if (data.career_development !== undefined) payload.career_development = data.career_development;
  if (data.salary_review !== undefined) payload.salary_review = data.salary_review;
  if (data.overall_rating !== undefined) payload.overall_rating = data.overall_rating;
  if (data.next_review_date !== undefined) payload.next_review_date = data.next_review_date;
  return apiClient.put<AnnualReview>(`/api/annual-reviews/${reviewId}`, payload);
};

export const markAsCompleted = (reviewId: string) => {
  return apiClient.post<AnnualReview>(
    `/api/annual-reviews/${reviewId}/mark-completed`
  );
};

export const acceptReview = (reviewId: string) => {
  return apiClient.put<AnnualReview>(`/api/annual-reviews/${reviewId}`, {
    employee_acceptance_status: "accepte",
  });
};

export const refuseReview = (reviewId: string) => {
  return apiClient.put<AnnualReview>(`/api/annual-reviews/${reviewId}`, {
    employee_acceptance_status: "refuse",
  });
};

export const deleteAnnualReview = (reviewId: string) => {
  return apiClient.delete(`/api/annual-reviews/${reviewId}`);
};

export const downloadAnnualReviewPdf = async (reviewId: string) => {
  const response = await apiClient.get(`/api/annual-reviews/${reviewId}/pdf`, {
    responseType: 'blob',
  });
  return response.data;
};
