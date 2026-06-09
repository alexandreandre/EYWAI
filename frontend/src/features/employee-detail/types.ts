export interface Employee {
  id: string; 
  first_name: string; 
  last_name: string; 
  job_title: string; 
  contract_type: string; 
  statut: string; 
  hire_date: string;
  email?: string | null;
  username?: string | null;
  employment_status?: string | null;
  current_exit_id?: string | null;
  exit_last_working_day?: string | null;
  exit_type?: string | null;
  exit_status?: string | null;
  // Titre de séjour (données calculées par le backend)
  is_subject_to_residence_permit?: boolean | null;
  residence_permit_status?: "valid" | "to_renew" | "expired" | "to_complete" | null;
  residence_permit_expiry_date?: string | null;
  residence_permit_days_remaining?: number | null;
  residence_permit_data_complete?: boolean | null;
  residence_permit_type?: string | null;
  residence_permit_number?: string | null;
  // Entretien courant (données calculées par le backend)
  annual_review_current_status?: string | null;
  annual_review_current_year?: number | null;
  annual_review_current_planned_date?: string | null;
  annual_review_current_completed_date?: string | null;
  collective_agreement_id?: string | null;
  college_electoral?: string | null;
  statut_cse?: string | null;
  heures_delegation_mensuelles?: number | null;
  salaire_de_base?: unknown;
  duree_hebdomadaire?: unknown;
  lieu_travail?: unknown;
  workplace?: unknown;
  poste?: string | null;
  weekly_hours?: unknown;
  team_id?: string | null;
}

