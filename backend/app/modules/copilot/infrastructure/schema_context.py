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
  - selected_days (array of dates): Liste des jours d'absence.
    -- USAGE: Utiliser array_length(selected_days, 1) pour compter le nombre de jours.
    -- USAGE: Pour vérifier si un jour est inclus : '2025-10-20'::date = ANY(selected_days)

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

Table 'expense_reports': Notes de frais.
  - employee_id, date, amount, type, status (pending/validated/rejected)

Table 'monthly_inputs': Primes et éléments variables de paie.
  - employee_id, year, month, name, amount

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
