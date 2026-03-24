"""
Constantes de schéma BDD exposées au LLM (Text-to-SQL et Agent).

Comportement strictement identique au legacy. Utilisées par OpenAIProvider.
"""

DATABASE_SCHEMA_TEXT_TO_SQL = """
Tu es un expert en génération de SQL PostgreSQL. Tu dois répondre aux questions en te basant **uniquement** sur le schéma suivant.
La date actuelle est {today}.

--- SCHÉMA DE LA BASE DE DONNÉES ---

Table 'employees': Stocke les informations permanentes sur les employés.
  - id (uuid, primary key): Identifiant unique de l'employé.
  - first_name (text): Prénom.
  - last_name (text): Nom de famille.
  - email (text): Email professionnel.
  - hire_date (date): Date d'embauche. Cruciale pour calculer l'ancienneté.
  - date_naissance (date): Date de naissance.
  - contract_type (text): Type de contrat (ex: 'CDI', 'CDD').
  - statut (text): Statut (Valeurs possibles: 'Cadre', 'Non-Cadre'). Très important pour les filtres.
  - job_title (text): Intitulé de poste.
  - is_temps_partiel (boolean): Vrai si l'employé est à temps partiel.
  - duree_hebdomadaire (numeric): Heures de travail par semaine (ex: 35, 39).
  
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
  - amount (numeric): Montant de la dépense en euros.
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
Table 'profiles': Stocke les informations de compte utilisateur.
  - id (uuid, primary key): Identifiant (jointure sur employees.id).
  - first_name (text): Prénom.
  - last_name (text): Nom.
  - role (text): Rôle (Valeurs: 'rh', 'collaborateur', 'collaborateur_rh').
"""

DATABASE_SCHEMA_AGENT = """
Table 'employees': Informations permanentes sur les employés.
  - id (uuid), first_name (text), last_name (text), email (text), company_id (uuid)
  - hire_date (date), date_naissance (date), contract_type (text: CDI/CDD)
  - statut (text: Cadre/Non-Cadre), job_title (text)
  - is_temps_partiel (boolean), duree_hebdomadaire (numeric)
  - salaire_de_base (jsonb): {"valeur": 2365.66}
  - adresse (jsonb): {"rue": "...", "ville": "...", "code_postal": "..."}
  - classification_conventionnelle (jsonb): {"coefficient": 240, "classe_emploi": 6}
  - specificites_paie (jsonb): Mutuelle, prévoyance, prélèvement à la source

Table 'payslips': Bulletins de paie (un par mois/employé).
  - id (uuid), employee_id (uuid), month (int 1-12), year (int)
  - payslip_data (jsonb): {"net_a_payer": ..., "salaire_brut": ..., "cout_total_employeur": ...}

Table 'absence_requests': Demandes d'absence.
  - id (uuid), employee_id (uuid)
  - type (text: conge_paye/rtt/maladie/sans_solde)
  - status (text: pending/validated/rejected)
  - selected_days (array of dates)

Table 'expense_reports': Notes de frais.
  - id (uuid), employee_id (uuid), date (date), amount (numeric)
  - type (text: Transport/Restaurant/Hôtel/Autre)
  - status (text: pending/validated/rejected)

Table 'monthly_inputs': Éléments variables de paie (primes, déductions).
  - id (uuid), employee_id (uuid), year (int), month (int)
  - name (text), amount (numeric)
  - is_socially_taxed (boolean), is_taxable (boolean)

Table 'employee_schedules': Cumuls et plannings mensuels.
  - id (uuid), employee_id (uuid), year (int), month (int)
  - cumuls (jsonb), planned_calendar (jsonb), actual_hours (jsonb)

Table 'collective_agreements_catalog': Catalogue des conventions collectives.
  - id (uuid), name (text), idcc (text), description (text)
  - sector (text), effective_date (date), is_active (boolean)
  - rules_pdf_path (text)

Table 'company_collective_agreements': Assignations de conventions collectives aux entreprises.
  - id (uuid), company_id (uuid), collective_agreement_id (uuid)
  - assigned_at (timestamp), assigned_by (uuid)

Table 'collective_agreement_texts': Cache des textes extraits des PDFs de conventions collectives.
  - id (uuid), agreement_id (uuid), full_text (text)
  - character_count (int), created_at (timestamp), updated_at (timestamp)
  - NOTE: Cette table contient le texte complet extrait des PDFs de conventions collectives
"""
