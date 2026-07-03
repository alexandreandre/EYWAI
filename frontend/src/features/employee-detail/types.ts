export interface Employee {
  id: string; 
  first_name: string; 
  last_name: string; 
  job_title: string; 
  contract_type: string; 
  statut: string; 
  is_forfait_jour?: boolean | null;
  hire_date: string;
  contract_end_date?: string | null;
  is_temps_partiel?: boolean | null;
  classification_conventionnelle?: {
    groupe_emploi?: string;
    classe_emploi?: number;
    coefficient?: number;
  } | null;
  prior_service_months?: number | null;
  seniority_reference_date?: string | null;
  email?: string | null;
  phone_number?: string | null;
  salary_payment_method?: 'virement' | 'cheque' | 'especes' | null;
  username?: string | null;
  nir?: string | null;
  date_naissance?: string | null;
  lieu_naissance?: string | null;
  nationalite?: string | null;
  adresse?: {
    rue?: string;
    voie?: string;
    code_postal?: string;
    ville?: string;
  } | null;
  coordonnees_bancaires?: {
    iban?: string;
    bic?: string;
  } | null;
  employment_status?: string | null;
  current_exit_id?: string | null;
  exit_last_working_day?: string | null;
  exit_type?: string | null;
  exit_status?: string | null;
  profile_complete?: boolean | null;
  missing_payroll_fields?: string[] | null;
  time_tracking_id?: string | null;
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
  salaire_de_base?: {
    valeur?: number;
    montant?: number;
  } | null;
  duree_hebdomadaire?: number | null;
  lieu_travail?: unknown;
  workplace?: unknown;
  poste?: string | null;
  weekly_hours?: unknown;
  team_id?: string | null;
  periode_essai?: Record<string, unknown> | null;
  trial_period_applicable?: boolean | null;
  trial_period_status?:
    | "in_progress"
    | "ending_soon"
    | "ended"
    | "confirmed"
    | "to_complete"
    | null;
  trial_period_end_date?: string | null;
  trial_period_days_remaining?: number | null;
  trial_period_renewal_possible?: boolean | null;
  specificites_paie?: {
    prelevement_a_la_source?: {
      is_personnalise?: boolean;
      taux?: number | null;
    };
    transport?: { abonnement_mensuel_total?: number };
    titres_restaurant?: { beneficie?: boolean; nombre_par_mois?: number };
    personnel_rd_eligible_jei?: boolean;
    mandataire_rd?: boolean;
    mutuelle?: {
      adhesion?: boolean;
      mutuelle_type_ids?: string[];
      lignes_specifiques?: Array<{ libelle?: string; montant_salarial?: number }>;
    };
    prevoyance?: {
      adhesion?: boolean;
      lignes_specifiques?: Array<{ libelle?: string; salarial?: number }>;
    };
    [key: string]: unknown;
  } | null;
}
