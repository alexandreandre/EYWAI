# Inventaire tables Supabase — périmètre RH copilot

Cocher chaque table présente dans `DATABASE_SCHEMA_AGENT` et `DATABASE_SCHEMA_TEXT_TO_SQL`.
**Obligatoire** = requêtable par un RH au quotidien.

## Effectifs & contrats

| Table | Obligatoire | Colonnes clés à documenter |
|-------|-------------|----------------------------|
| `employees` | ✅ | id, company_id, first_name, last_name, email, hire_date, date_naissance, contract_type, statut (Cadre/Non-Cadre/parti/en_onboarding), job_title, is_temps_partiel, duree_hebdomadaire, salaire_de_base (jsonb), adresse, coordonnees_bancaires, classification_conventionnelle, specificites_paie, periode_essai, avantages_en_nature |
| `profiles` | ✅ | id, role (rh/collaborateur/collaborateur_rh), first_name, last_name |
| `companies` | ✅ | id, company_name, is_active, modules activés si colonnes existent |
| `user_company_accesses` | optionnel | Accès multi-entreprises RH |
| `teams` | ✅ | id, company_id, name, manager_id |
| `salary_history` | ✅ | employee_id, effective_date, montant, motif |
| `employee_exits` | ✅ | employee_id, exit_type, exit_date, status |

## Paie & rémunération

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `payslips` | ✅ | employee_id, month, year, payslip_data (jsonb : salaire_brut, net_a_payer, cout_total_employeur, synthese_net) |
| `employee_schedules` | ✅ | employee_id, year, month, cumuls, planned_calendar, actual_hours (jsonb) |
| `monthly_inputs` | ✅ | employee_id, year, month, name, amount, is_socially_taxed, is_taxable |
| `salary_advances` | ✅ | employee_id, amount, status, request_date, type (si migration types) |
| `employee_loans` | ✅ | employee_id, principal, status, start_date |
| `employee_loan_installments` | optionnel | loan_id, due_date, amount, status |
| `salary_seizures` | ✅ | employee_id, type (pension/ATD…), amount, status |

## Absences & temps

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `absence_requests` | ✅ | employee_id, type (conge_paye/rtt/maladie/sans_solde…), status, selected_days (array) |
| `employee_time_entries` | optionnel | employee_id, clock_in, clock_out (badgeuse) |
| `shifts` / `shift_types` | optionnel | Planning équipes |

## Notes de frais & dépenses

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `expense_reports` | ✅ | employee_id, date, amount, amount_ht, vat_amount, vat_rate, type, status |

## Recrutement & onboarding

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `recruitment_candidates` | ✅ | company_id, first_name, last_name, stage, ai_score, status |
| `recruitment_jobs` | ✅ | company_id, title, status |
| `onboarding_checklists` | ✅ | employee_id, status |
| `onboarding_tasks` | ✅ | checklist_id, title, completed, category |

## Formation & carrière

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `training_enrollments` | ✅ | employee_id, training_id, status, dates |
| `training_catalog` | ✅ | company_id, title, duration_hours |
| `annual_reviews` | ✅ | employee_id, year, status, review_date |
| `employee_objectives` | optionnel | employee_id, title, status, progress |
| `employee_competencies` | optionnel | employee_id, competency_id, level |
| `promotions` / tables augmentations | ✅ | employee_id, effective_date, new_salary (selon schéma réel) |

## Documents & conformité

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `documents` | ✅ | employee_id, category, title, status |
| `residence_permits` | ✅ | employee_id, expiry_date, status, type |
| `employee_certifications` | optionnel | employee_id, certification_id, expiry_date |

## Médical

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `medical_appointments` | ✅ | employee_id, appointment_date, type, status |
| `medical_obligations` | optionnel | employee_id, next_due_date, type |

## CSE & dialogue social

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `cse_meetings` | optionnel | company_id, date, status |
| `cse_delegation_requests` | optionnel | employee_id, hours, status |

## Conventions collectives (déjà partiellement documentées)

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `collective_agreements_catalog` | ✅ | name, idcc, sector |
| `company_collective_agreements` | ✅ | company_id, collective_agreement_id |
| `collective_agreement_texts` | ✅ | agreement_id, full_text |
| `convention_collective_rules` | optionnel | agreement_id, rule_type, extracted_value |

## Notifications & signatures

| Table | Obligatoire | Colonnes clés |
|-------|-------------|---------------|
| `notifications` | optionnel | user_id, type, read, created_at |
| Tables signatures (docuseal ou équivalent) | optionnel | status pending/signed |

---

## Modèle de documentation par table (copier dans schema_context.py)

```
Table 'employees': Fiche salarié — source principale effectifs et contrat.
  - id (uuid, PK), company_id (uuid, FK companies.id) — TOUJOURS filtrer par company_id
  - first_name, last_name, email (text)
  - hire_date (date), contract_type (text: 'CDI', 'CDD', 'Apprenti'…)
  - statut (text: 'Cadre', 'Non-Cadre', 'parti', 'en_onboarding')
  - salaire_de_base (jsonb): {"valeur": 2500.00}
    Usage: (salaire_de_base->>'valeur')::numeric
  - specificites_paie (jsonb): mutuelle, prevoyance, prelevement_a_la_source
    Usage: (specificites_paie->'prelevement_a_la_source'->>'taux')::numeric
```

## Jointures fréquentes (inclure dans le schéma)

```sql
-- Effectif avec dernier bulletin
employees e
JOIN payslips p ON p.employee_id = e.id
WHERE e.company_id = '<company_id>'

-- Absences du mois
absence_requests ar
JOIN employees e ON ar.employee_id = e.id
WHERE e.company_id = '<company_id>'
  AND ar.status = 'validated'
  AND '<date>'::date = ANY(ar.selected_days)
```

## Vérification complétude

Après mise à jour, compter les tables obligatoires ✅ documentées :

```bash
rg "^Table '" backend/app/modules/copilot/infrastructure/schema_context.py
```

Objectif : **≥ 15 tables** dans `DATABASE_SCHEMA_AGENT`, détail JSONB complet dans `DATABASE_SCHEMA_TEXT_TO_SQL`.
