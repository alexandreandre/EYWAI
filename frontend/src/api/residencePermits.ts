// src/api/residencePermits.ts
// API pour la page Titres de séjour (liste RH)

import apiClient from "./apiClient";

export type ResidencePermitStatus =
  | "valid"
  | "to_renew"
  | "expired"
  | "to_complete";

export interface ResidencePermitListItem {
  employee_id: string;
  first_name: string;
  last_name: string;
  is_subject_to_residence_permit: boolean;
  residence_permit_status: ResidencePermitStatus | null;
  residence_permit_expiry_date: string | null;
  residence_permit_days_remaining: number | null;
  residence_permit_data_complete: boolean | null;
  residence_permit_type: string | null;
  residence_permit_number: string | null;
}

/**
 * Récupère la liste des titres de séjour pour l'entreprise active.
 * Le backend filtre sur is_subject_to_residence_permit = true et employment_status actif/en_sortie.
 */
export const getResidencePermits = () => {
  return apiClient.get<ResidencePermitListItem[]>("/api/residence-permits");
};
