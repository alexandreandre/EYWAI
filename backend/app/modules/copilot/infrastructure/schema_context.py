"""
Constantes de schéma BDD exposées au LLM (Text-to-SQL et Agent).

Comportement strictement identique au legacy. Utilisées par OpenAIProvider.
"""

DATABASE_SCHEMA_TEXT_TO_SQL = """
Tu es un expert en génération de SQL PostgreSQL. Tu dois répondre aux questions en te basant **uniquement** sur le schéma suivant.
La date actuelle est {today}.

IMPORTANT: Toute requête sur employees ou table liée DOIT filtrer via
employees.company_id = '<company_id>' (jointure employees si besoin).
Effectif actif : employment_status IN ('actif', 'active', 'en_onboarding').

--- SCHÉMA DE LA BASE DE DONNÉES ---

Table 'employees': Fiche salarié — source principale effectifs et contrat.
  - id (uuid, PK), company_id (uuid, FK companies.id) — TOUJOURS filtrer.
  - first_name (text): Prénom.
  - last_name (text): Nom de famille.
  - email (text): Email professionnel.
  - hire_date (date): Date d'embauche. Cruciale pour calculer l'ancienneté.
  - seniority_reference_date (date): Date de référence ancienneté (reprise / accord).
  - date_naissance (date): Date de naissance.
  - contract_type (text): Type de contrat (ex: 'CDI', 'CDD', 'Apprenti').
  - statut (text): Classification (Valeurs: 'Cadre', 'Non-Cadre').
  - employment_status (text): Statut RH (Valeurs: 'actif', 'active', 'en_onboarding',
    'en_sortie', 'parti', 'inactif'). Utiliser 'parti' pour les sorties archivées.
  - job_title (text): Intitulé de poste.
  - is_temps_partiel (boolean): Vrai si l'employé est à temps partiel.
  - duree_hebdomadaire (numeric): Heures de travail par semaine (ex: 35, 39).
  - prior_service_months (int): Mois de carrière antérieurs (médailles du travail).
  - is_subject_to_residence_permit (boolean): Soumis au titre de séjour.
  - residence_permit_expiry_date (date): Échéance titre de séjour.
  - residence_permit_type (text): Type de titre.
  
  -- Colonnes JSONB de 'employees' (Utiliser ->> pour interroger)
  - salaire_de_base (jsonb): Contient le salaire brut.
    -- Structure: {"valeur": 2365.66}
    -- Usage SQL: (salaire_de_base->>'valeur')::numeric
  
  - adresse (jsonb): Adresse postale.
    -- Structure: {"rue": "2 Rue Galilée", "ville": "Champs-sur-Marne", "code_postal": "77420"}
    -- Usage SQL: (adresse->>'ville'), (adresse->>'code_postal')
    
  - coordonnees_bancaires (jsonb): Informations bancaires.
    -- Structure: {"bic": "187687698", "iban": "FR76187618761876"}
    -- Usage SQL: (coordonnees_bancaires->>'iban')
  
  - periode_essai (jsonb): (Peut être NULL) Détails de la période d'essai.
    -- Structure: {"duree_initiale_mois": 3, "date_fin": "2025-01-18"}
    
  - classification_conventionnelle (jsonb): Infos de la convention (ex: Syntec).
    -- Structure: {"coefficient": 240, "classe_emploi": 6, "groupe_emploi": "C"}
    -- Usage SQL: (classification_conventionnelle->>'coefficient')::int
    
  - avantages_en_nature (jsonb): Avantages (repas, logement, voiture).
    -- Structure: {"repas": {"nombre_par_mois": 0}, "logement": {"beneficie": false}}
    
  - specificites_paie (jsonb): Le plus important. Contient les adhésions et taux personnalisés.
    -- Structure: {"mutuelle": {"adhesion": true, ...}, "prevoyance": {"adhesion": true, ...}, "prelevement_a_la_source": {"taux": 5, ...}}
    -- Usage SQL: (specificites_paie->'prevoyance'->>'adhesion')::boolean, (specificites_paie->'prelevement_a_la_source'->>'taux')::numeric

---
Table 'payslips': Stocke les bulletins de paie générés (un par mois/employé). C'est la source principale pour les données financières passées.
  - id (uuid, primary key): Identifiant du bulletin.
  - employee_id (uuid, foreign key to employees.id): ID de l'employé.
  - month (int): Mois (1-12).
  - year (int): Année.
  - payslip_data (jsonb): Données JSON du bulletin.
    -- Structure: {"net_a_payer": 3410.69, "salaire_brut": 1710.56, "cout_total_employeur": 3823.82, ...}
    -- USAGE CRUCIAL (JSONB):
    -- Salaire Brut: (payslip_data->>'salaire_brut')::numeric
    -- Net à Payer: (payslip_data->>'net_a_payer')::numeric
    -- Coût Total Employeur: (payslip_data->'pied_de_page'->>'cout_total_employeur')::numeric
    -- Net Imposable: (payslip_data->'synthese_net'->>'net_imposable')::numeric

---
Table 'absence_requests': Stocke toutes les demandes d'absence des employés.
  - id (uuid, primary key): Identifiant de l'absence.
  - employee_id (uuid, foreign key to employees.id): ID de l'employé.
  - type (text): Type d'absence (Valeurs: 'conge_paye', 'rtt', 'maladie', 'sans_solde').
  - status (text): Statut (Valeurs: 'pending', 'validated', 'rejected', 'cancelled').
  - subrogation_active (boolean): Subrogation IJSS pour cet arrêt (null = défaut entreprise).
  - arret_type (text): Type d'arrêt maladie si applicable.
  - selected_days (array of dates): Liste des jours d'absence.
    -- USAGE: Utiliser array_length(selected_days, 1) pour compter le nombre de jours.
    -- USAGE: Pour vérifier si un jour est inclus : '2025-10-20'::date = ANY(selected_days)

---
Table 'company_leave_settings': Paramètres congés payés et RTT par entreprise.
  - company_id (uuid, UNIQUE), cp_counting_unit (text: 'ouvrable', 'ouvre')
  - cp_acquisition_days_per_month (numeric), rtt_annual_days (numeric)
  - rtt_use_calendar_formula (boolean), rtt_use_forfait_jours_formula (boolean)
  - rtt_forfait_annual_days (int), rtt_forfait_cp_ouvres_deduction (numeric)
  - rtt_year_end_reminder_enabled (boolean)

---
Table 'employee_leave_adjustments': Soldes d'ouverture CP/RTT par salarié et année.
  - employee_id (uuid), year (int)
  - cp_n1_opening_balance (numeric), cp_n_opening_balance (numeric)
  - rtt_opening_balance (numeric), rtt_forfeited_days (numeric)

---
Table 'salary_certificates': Attestations de salaire (Cerfa) pour arrêts IJSS.
  - employee_id (uuid), absence_request_id (uuid), company_id (uuid)
  - transmitted_to_cpam (boolean), transmission_date (timestamptz)

---
Table 'ijss_tracking_periods': Périodes mensuelles de rapprochement IJSS.
  - company_id (uuid), period_year (int), period_month (int)
  - status (text): 'open', 'partial', 'reconciled', 'closed'
  - expected_total, received_cpam_total, received_bank_total, variance_total (numeric)

---
Table 'ijss_expected_lines': IJSS théoriques par salarié et période.
  - period_id (uuid), employee_id (uuid), absence_request_id (uuid)
  - ijss_theorique (numeric), ijss_subrogees_bulletin (numeric)
  - line_status (text): 'pending', 'partial', 'ok', 'variance', 'justified'

---
Table 'ijss_received_lines': IJSS reçues (CPAM, virement, saisie manuelle).
  - period_id (uuid), employee_id (uuid), source (text: 'cpam_decompte', 'bank_transfer', 'manual')
  - amount (numeric), match_status (text): 'unmatched', 'matched', 'disputed'

---
Table 'company_overtime_contingent_settings': Paramètres contingent HS entreprise.
  - company_id (uuid), legal_cor_contingent_hours (numeric, défaut 220)
  - management_contingent_hours (numeric), hours_per_rest_day (numeric)

---
Table 'employee_overtime_adjustments': Solde d'ouverture contingent HS par salarié.
  - employee_id (uuid), year (int), opening_balance_hours (numeric)

---
Table 'company_modulation_settings': Paramètres modulation / annualisation et compte d'heures.
  - company_id (uuid), enabled (boolean)
  - average_weekly_hours, weekly_high_hours, weekly_low_hours (numeric)
  - high_weeks_per_cycle, low_weeks_per_cycle (int)
  - hour_account_enabled (boolean), hs_franchise_hours_per_period (numeric)
  - hs_routing_policy (text: pay_all, account_all, franchise, manual)
  - hs_franchise_period (text: 'month', 'pay_period')
  - max_account_balance_hours (numeric), recovery_absence_enabled (boolean)

---
Table 'employee_modulation_movements': Grand livre compte modulation (comme CET).
  - employee_id (uuid), year (int), month (int)
  - movement_type (text): 'credit_hs', 'debit_recovery', 'debit_payout', 'adjustment', 'opening_balance'
  - hours (numeric), status (text): 'pending', 'validated', 'applied_payroll', 'cancelled'

---
Table 'employee_modulation_counters': Cache compteurs modulation par salarié et année.
  - employee_id (uuid), year (int)
  - theoretical_hours, actual_hours, balance_hours (numeric)
  - account_balance_hours (numeric), period_credited_hours, period_paid_hours (numeric)

---
Table 'company_cet_settings': Paramètres compte épargne-temps (CET).
  - company_id (uuid), cet_enabled (boolean)
  - validation_mode (text): 'auto', 'rh', 'manager', 'manager_then_rh'
  - allow_deposit_hs, allow_deposit_cp (boolean)
  - max_cp_days_per_year, max_account_balance_days (numeric, nullable)
  - cp_unit ('ouvres'|'ouvrables'), cp_debit_timing, hs_debit_timing

---
Table 'employee_cet_movements': Mouvements CET (dépôt HS/CP, retrait, ajustement).
  - employee_id (uuid), year (int), month (int)
  - movement_type (text): 'deposit_hs', 'deposit_cp', 'withdraw_rest', 'adjustment'
  - hours (numeric), days (numeric), status (text): 'pending', 'validated', 'rejected', 'applied_payroll'
  - workflow_step (text): 'pending', 'pending_manager', 'approved_manager', 'rejected_manager', 'approved_rh', 'rejected_rh'
  - manager_id, manager_approved_at, manager_rejected_at

---
Table 'participation_campaigns': Campagnes bulletin d'option participation/intéressement.
  - company_id (uuid), year (int), status (text): 'draft', 'open', 'closed'
  - deadline_at (timestamptz), payroll_year (int), payroll_month (int)

---
Table 'participation_bulletins': Bulletins d'option par salarié et campagne.
  - campaign_id (uuid), employee_id (uuid), company_id (uuid)
  - dispositif_type (text): 'participation', 'interessement'
  - status (text): 'draft', 'sent', 'responded', 'late', 'default_pee'
  - gross_amount (numeric), choice_type (text)

---
Table 'expense_reports': Stocke les notes de frais soumises par les employés.
  - id (uuid, primary key): Identifiant de la note de frais.
  - employee_id (uuid, foreign key to employees.id): ID de l'employé.
  - date (date): Date de la dépense.
  - amount (numeric): Montant TTC de la dépense en euros.
  - vat_rate (numeric): Taux de TVA en pourcentage (ex. 20, 10, 5.5).
  - amount_ht (numeric): Montant HT calculé.
  - vat_amount (numeric): Montant de TVA en euros.
  - type (text): Type de dépense (Valeurs: 'Transport', 'Restaurant', 'Hôtel', 'Autre').
  - status (text): Statut (Valeurs: 'pending', 'validated', 'rejected').

---
Table 'monthly_inputs': Stocke les éléments variables de paie (primes, déductions) pour un mois donné.
  - id (uuid, primary key): Identifiant de la saisie.
  - employee_id (uuid, foreign key to employees.id): ID de l'employé.
  - year (int): Année.
  - month (int): Mois.
  - name (text): Nom de la prime (ex: "Prime d'assiduité").
  - amount (numeric): Montant de la prime en euros.
  - is_socially_taxed (boolean): Soumis aux cotisations sociales.
  - is_taxable (boolean): Soumis à l'impôt.
  - bonus_type_id (uuid, FK company_bonus_types.id): Lien catalogue prime entreprise.
  - catalog_prime_id (text): Code prime moteur paie si applicable.
  - payroll_quantity (numeric): Quantité (heures, semaines, km…) pour primes calculées.
  - export_code (text): Code export compta / DSN.

---
Table 'company_bonus_types': Catalogue des types de primes entreprise.
  - id (uuid, PK), company_id (uuid, FK companies.id)
  - libelle (text), type (text): 'montant_fixe', 'selon_heures'
  - montant (numeric), seuil_heures (numeric): seuil pour type selon_heures
  - soumise_a_cotisations (boolean), soumise_a_impot (boolean)
  - export_code (text): code export paie/compta

---
Table 'company_payroll_variable_rules': Règles de génération automatique des variables de paie.
  - id (uuid, PK), company_id (uuid), code (text), label (text), enabled (boolean)
  - rule_type (text): 'fixed_monthly', 'per_astreinte_week', 'per_shift_type',
    'per_modulation_payout', 'per_night_hour', 'per_astreinte_weekend_km',
    'per_astreinte_week_tiered', 'per_astreinte_weekend_majoration', 'per_week_without_absence'
  - bonus_type_id (uuid), amount (numeric), rate (numeric)
  - conditions (jsonb): critères métier. Usage: (conditions->>'cle')::type
  - generation_mode (text): 'auto', 'suggest'

---
Table 'employee_time_entries': Pointages badgeuse bruts (entrées/sorties).
  - id (uuid, PK), employee_id (uuid), company_id (uuid)
  - timestamp (timestamptz), event_type (text): 'ENTREE', 'SORTIE'
  - source (text): 'EMPLOYE', 'RH', 'QR_SCAN'
  - Jointure: employees e ON e.id = employee_time_entries.employee_id WHERE e.company_id = ...

---
Table 'employee_time_day_accounting': Heures comptabilisées par jour (override RH, distinct du brut).
  - employee_id (uuid), company_id (uuid), day (date)
  - accounted_seconds (int): 0–86400. Usage: accounted_seconds / 3600.0 pour heures

---
Table 'employee_time_entries_validations': Validation RH d'une journée de pointages.
  - employee_id (uuid), company_id (uuid), day (date), validated_by (uuid)

---
Table 'company_punch_accounting_settings': Paramètres comptabilisation pointages par entreprise.
  - company_id (uuid, PK), enabled (boolean)
  - tolerance_minutes (int), default_break_deduct_minutes (int)
  - slot_detection (text): 'shift_code', 'nearest_entry', 'planning_first'
  - within_tolerance_pay_theoretical (boolean)
  - require_manager_validation_for_overtime (boolean)

---
Table 'employee_punch_overtime_reviews': HS détectées à la badgeuse, validation jour par jour.
  - employee_id (uuid), company_id (uuid), work_date (date)
  - overtime_hours (numeric), reason (text): 'early_entry', 'late_exit', 'daily_excess'
  - status (text): 'pending', 'approved', 'rejected'

---
Table 'employee_overtime_routing_decisions': Décisions mensuelles répartition HS payer vs compte (politique manual).
  - employee_id (uuid), company_id (uuid), year (int), month (int)
  - total_hs_hours, hours_to_pay, hours_to_account (numeric)
  - status (text): 'pending', 'validated', 'applied_payroll'

---
Table 'company_work_time_periods': Périodes de référence horaire (activité réduite, horaire transitoire).
  - company_id (uuid), label (text), start_date (date), end_date (date)
  - daily_reference_hours, weekly_reference_hours (numeric)
  - affects_payroll (boolean), affects_planning (boolean), is_active (boolean)

---
Table 'employee_schedules': Stocke les cumuls de paie et les plannings mensuels.
  - id (uuid, primary key): Identifiant de l'entrée.
  - employee_id (uuid, foreign key to employees.id): ID de l'employé.
  - year (int): Année.
  - month (int): Mois.
  - cumuls (jsonb): (Peut être NULL) Cumuls de paie de fin de mois.
    -- Structure: {"periode": {...}, "cumuls": {"brut_total": 2365.66, "net_imposable": 1207.83, "impot_preleve_a_la_source": 60.39, ...}}
    -- Usage SQL: (cumuls->'cumuls'->>'brut_total')::numeric
  
  - planned_calendar (jsonb): Planning théorique.
    -- Structure: {"periode": {...}, "calendrier_prevu": [{"jour": 1, "type": "travail", "heures_prevues": 8}, ...]}
    
  - actual_hours (jsonb): Heures réelles pointées.
    -- Structure: {"periode": {...}, "calendrier_reel": [{"jour": 1, "type": "travail", "heures_faites": 8}, ...]}

---
Table 'salary_advances': Avances et acomptes sur salaire ou prime.
  - id (uuid, PK), company_id (uuid), employee_id (uuid, FK employees.id)
  - advance_type (text): 'avance_salaire', 'acompte_salaire', 'acompte_prime'
  - requested_amount (numeric), approved_amount (numeric), remaining_amount (numeric)
  - requested_date (date), payment_date (date)
  - status (text): 'pending', 'approved', 'rejected', 'paid'
  - repayment_mode (text): 'single', 'multiple'
  - prime_label (text), prime_expected_amount (numeric) — pour acompte_prime
  - Jointure: employees e ON e.id = salary_advances.employee_id WHERE e.company_id = ...

---
Table 'salary_seizures': Saisies sur salaire (arrêts, pensions, ATD).
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - type (text): 'saisie_arret', 'pension_alimentaire', 'atd', 'satd'
  - status (text): 'active', 'suspended', 'closed'
  - amount (numeric), calculation_mode (text): 'fixe', 'pourcentage', 'barème_legal'
  - start_date (date), end_date (date), creditor_name (text)

---
Table 'employee_loans': Prêts employeur accordés aux salariés.
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - principal_amount (numeric), annual_interest_rate (numeric)
  - start_date (date), duration_months (int), monthly_payment (numeric)
  - status (text): 'draft', 'active', 'suspended', 'repaid', 'cancelled', 'defaulted'
  - remaining_capital (numeric)

---
Table 'employee_loan_installments': Échéancier prévisionnel d'un prêt.
  - loan_id (uuid, FK employee_loans.id), year (int), month (int)
  - total_due (numeric), status (text): 'pending', 'paid', 'skipped'

---
Table 'salary_history': Historique des évolutions de salaire.
  - employee_id (uuid), company_id (uuid), effective_date (date), motif (text)
  - ancien_salaire (jsonb): {"valeur": 2500.00}
  - nouveau_salaire (jsonb): {"valeur": 2700.00}
  - Usage: (nouveau_salaire->>'valeur')::numeric

---
Table 'employee_exits': Procédures de départ des salariés.
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - exit_type (text): 'demission', 'rupture_conventionnelle', 'licenciement',
    'depart_retraite', 'fin_periode_essai'
  - status (text): workflow départ (ex: 'demission_effective', 'archivee', 'annulee')
  - last_working_day (date), notice_end_date (date)

---
Table 'teams': Équipes de l'entreprise.
  - id (uuid, PK), company_id (uuid), name (text), manager_id (uuid, FK employees.id)

---
Table 'companies': Entreprises clientes.
  - id (uuid, PK), company_name (text), is_active (boolean), group_id (uuid)
  - dsn_sync_mode (text): mode synchronisation DSN
  - service_sante_travail_nom, service_sante_travail_telephone, service_sante_travail_email (text)
  - service_sante_travail_adresse_rue, service_sante_travail_adresse_code_postal,
    service_sante_travail_adresse_ville (text)

---
Table 'recruitment_jobs': Offres de recrutement.
  - id (uuid, PK), company_id (uuid), title (text), status (text)

---
Table 'recruitment_candidates': Candidats en cours de recrutement.
  - id (uuid, PK), company_id (uuid), job_id (uuid), first_name (text), last_name (text)
  - ai_score (numeric): Score IA du candidat
  - current_stage_id (uuid): Étape pipeline actuelle

---
Table 'onboarding_checklists': Intégrations en cours.
  - id (uuid, PK), employee_id (uuid), company_id (uuid), completed_at (timestamptz)

---
Table 'onboarding_tasks': Tâches d'une checklist d'onboarding.
  - checklist_id (uuid), title (text), category (text), is_completed (boolean)

---
Table 'annual_reviews': Entretiens annuels et professionnels.
  - id (uuid, PK), employee_id (uuid), company_id (uuid), year (int)
  - status (text): 'planifie', 'en_attente_acceptation', 'accepte', 'refuse',
    'realise', 'cloture'
  - planned_date (date), completed_date (date)

---
Table 'promotions': Promotions et évolutions de carrière.
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - type (text): 'poste', 'salaire', 'statut', 'classification', 'mixte'
  - status (text): 'draft', 'pending_approval', 'approved', 'effective', 'cancelled'
  - effective_date (date)

---
Table 'training_catalog': Catalogue de formations.
  - id (uuid, PK), company_id (uuid), title (text), duration_hours (numeric)

---
Table 'training_enrollments': Inscriptions aux formations.
  - id (uuid, PK), employee_id (uuid), training_id (uuid)
  - status (text): ex. 'planifie', 'realise', 'approuve_rh', 'completed'

---
Table 'generated_documents': Documents RH générés (contrats, attestations, bulletins).
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - document_type (text), status (text): 'brouillon', 'envoye', 'signe'
  - created_at (timestamptz)

---
Table 'medical_follow_up_obligations': Obligations de visite médicale.
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - visit_type (text): ex. 'vip', 'sir', 'reprise'
  - due_date (date), status (text): 'a_faire', 'planifiee', 'realisee', 'annulee'

---
Table 'employee_work_medal_cases': Dossiers médailles du travail par salarié.
  - id (uuid, PK), company_id (uuid), employee_id (uuid)
  - medal_level (text): 'argent', 'vermeil', 'or', 'grand_or'
  - milestone_years (int): 20, 30, 35, 40
  - eligible_date (date), status (text): 'upcoming', 'awaiting_rh', 'approved', 'paid'
  - amount_computed (numeric)

---
Table 'profiles': Stocke les informations de compte utilisateur.
  - id (uuid, primary key): Identifiant (jointure sur employees.id).
  - first_name (text): Prénom.
  - last_name (text): Nom.
  - role (text): Rôle (Valeurs: 'rh', 'collaborateur', 'collaborateur_rh').
"""

DATABASE_SCHEMA_AGENT = """
IMPORTANT: Filtrer par company_id via employees ou colonne company_id directe.

Table 'employees': Fiche salarié (effectifs, contrat, paie).
  - id, company_id, first_name, last_name, email, hire_date, contract_type
  - statut (Cadre/Non-Cadre), employment_status (actif/parti/en_onboarding/…)
  - salaire_de_base (jsonb), specificites_paie (jsonb), periode_essai (jsonb)
  - is_temps_partiel, duree_hebdomadaire, prior_service_months
  - is_subject_to_residence_permit, residence_permit_expiry_date
  - Jointure: company_id = '<company_id>'

Table 'payslips': Bulletins de paie mensuels.
  - employee_id, month, year, payslip_data (jsonb: salaire_brut, net_a_payer, cout_total_employeur)

Table 'salary_history': Évolutions de salaire.
  - employee_id, effective_date, ancien_salaire/nouveau_salaire (jsonb), motif

Table 'salary_advances': Avances et acomptes.
  - employee_id, advance_type (avance_salaire/acompte_salaire/acompte_prime)
  - requested_amount, approved_amount, status (pending/approved/rejected/paid)

Table 'salary_seizures': Saisies sur salaire.
  - employee_id, type (saisie_arret/pension_alimentaire/atd), status (active/closed)

Table 'employee_loans': Prêts employeur.
  - employee_id, principal_amount, status (active/repaid/…), remaining_capital

Table 'absence_requests': Demandes d'absence.
  - employee_id, type (conge_paye/rtt/maladie/sans_solde), status, selected_days (array)
  - subrogation_active (boolean), arret_type (text)

Table 'company_leave_settings': Paramètres CP/RTT entreprise.
  - company_id, cp_counting_unit, rtt_annual_days, rtt_use_forfait_jours_formula

Table 'employee_leave_adjustments': Soldes ouverture CP/RTT par salarié.
  - employee_id, year, cp_n_opening_balance, rtt_opening_balance

Table 'ijss_tracking_periods': Rapprochement IJSS mensuel.
  - company_id, period_year, period_month, status (open/reconciled/closed)
  - expected_total, received_cpam_total, variance_total

Table 'ijss_expected_lines': IJSS théoriques par salarié.
  - period_id, employee_id, ijss_theorique, line_status

Table 'salary_certificates': Attestations salaire arrêts maladie.
  - employee_id, absence_request_id, transmitted_to_cpam

Table 'company_overtime_contingent_settings': Contingent HS entreprise.
  - company_id, legal_cor_contingent_hours, management_contingent_hours

Table 'employee_overtime_adjustments': Solde ouverture contingent HS.
  - employee_id, year, opening_balance_hours

Table 'company_modulation_settings': Modulation temps de travail et compte d'heures.
  - company_id, enabled, average_weekly_hours, weekly_high_hours, weekly_low_hours
  - hour_account_enabled, hs_franchise_hours_per_period, recovery_absence_enabled

Table 'employee_modulation_counters': Cache modulation par salarié (annualisation + compte).
  - employee_id, year, balance_hours, theoretical_hours, actual_hours, account_balance_hours

Table 'company_cet_settings': Paramètres CET (HS/CP, plafonds, validation manager/RH).
  - company_id, cet_enabled, validation_mode, allow_deposit_cp, max_cp_days_per_year

Table 'employee_cet_movements': Grand livre CET par salarié.
  - employee_id, year, month, movement_type, days, hours, status, workflow_step

Table 'participation_campaigns': Campagnes participation/intéressement.
  - company_id, year, status (draft/open/closed), deadline_at

Table 'participation_bulletins': Bulletins d'option salariés.
  - campaign_id, employee_id, status, gross_amount, choice_type

Table 'expense_reports': Notes de frais.
  - employee_id, date, amount, type, status (pending/validated/rejected)

Table 'monthly_inputs': Primes et éléments variables de paie.
  - employee_id, year, month, name, amount
  - bonus_type_id, payroll_quantity, export_code

Table 'company_bonus_types': Catalogue primes entreprise.
  - company_id, libelle, type (montant_fixe/selon_heures), montant, export_code

Table 'company_payroll_variable_rules': Règles génération variables paie (astreinte, équipes, présence…).
  - company_id, code, rule_type, bonus_type_id, amount, generation_mode

Table 'employee_time_entries': Pointages badgeuse bruts.
  - employee_id, company_id, timestamp, event_type (ENTREE/SORTIE), source

Table 'employee_time_day_accounting': Heures comptabilisées/jour (override RH).
  - employee_id, company_id, day, accounted_seconds

Table 'company_punch_accounting_settings': Paramètres comptabilisation pointages entreprise.
  - company_id, enabled, tolerance_minutes, slot_detection, require_manager_validation_for_overtime

Table 'employee_punch_overtime_reviews': HS badgeuse en attente validation.
  - employee_id, work_date, overtime_hours, status (pending/approved/rejected)

Table 'employee_overtime_routing_decisions': Répartition HS payer vs compte (modulation manual).
  - employee_id, year, month, total_hs_hours, hours_to_pay, hours_to_account, status

Table 'employee_schedules': Cumuls et plannings mensuels.
  - employee_id, year, month, cumuls (jsonb), actual_hours (jsonb)

Table 'employee_exits': Départs et sorties.
  - employee_id, exit_type, status, last_working_day

Table 'teams': Équipes.
  - company_id, name, manager_id

Table 'recruitment_candidates': Candidats.
  - company_id, job_id, first_name, last_name, ai_score, current_stage_id

Table 'onboarding_checklists': Onboardings.
  - employee_id, company_id, completed_at (+ onboarding_tasks: is_completed)

Table 'annual_reviews': Entretiens annuels.
  - employee_id, year, status (planifie/realise/cloture/…), planned_date

Table 'promotions': Promotions.
  - employee_id, type, status, effective_date

Table 'training_enrollments': Formations inscrites.
  - employee_id, training_id, status

Table 'training_budget': Budget formation annuel par entreprise.
  - company_id, year, global_envelope (numeric), service_breakdown (jsonb)

Table 'medical_follow_up_obligations': Visites médicales à planifier.
  - employee_id, due_date, status (a_faire/planifiee/realisee)

Table 'employee_work_medal_cases': Médailles du travail.
  - employee_id, medal_level, milestone_years, status, eligible_date

Table 'generated_documents': Documents générés.
  - employee_id, document_type, status

Table 'collective_agreements_catalog': Catalogue CC (id, name, idcc, sector).
Table 'company_collective_agreements': CC assignées (company_id, collective_agreement_id).
Table 'collective_agreement_texts': Texte CC extrait (agreement_id, full_text).
"""
