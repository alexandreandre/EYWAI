# Compensation des heures entre semaines : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une option société qui compte les heures sup et les heures manquantes comme Gaëlle : écarts journaliers, majorations par semaine (`min(T, 4)` à 25 %, le reste à 50 %), somme sur la fenêtre des variables semaines négatives comprises, jamais de retenue.

**Architecture:** Un module pur `compensation_semaines` (bilan, majorations, compensation, application à une liste d'événements). Le générateur l'applique aux événements de M et M-1 quand `settings.compensation_heures_entre_semaines` est vrai, après résolution de la fenêtre, et dépose le résumé dans les saisies ; le moteur écrit la mention et `payslip_data.compensation_semaines`. Un booléen dans le PATCH des réglages société et une carte dans l'onglet Paie.

**Tech Stack:** Python 3.12 / pytest / ruff (`backend/.venv/bin/python`) ; React + TypeScript + vitest + eslint.

Spec : `docs/superpowers/specs/2026-09-21-compensation-heures-entre-semaines-design.md`.

## Global Constraints

- Option désactivée : aucun événement, aucun montant ne change (tests existants intacts).
- Le module pur ne lit ni base ni fichier ; le générateur lui passe ce qu'il a déjà (`planned_data_all_months`, `actual_data_all_months`, `duree_hebdo`, fenêtre).
- Aucun commit sans demande explicite d'Alexandre.
- Les deux rouges d'environnement (`test_app_env_defaut_est_prod`, `test_api_failure_manual_fallback`) ne comptent pas.

---

### Task 1: Le module pur `compensation_semaines`

**Files:**
- Create: `backend/app/modules/payroll/application/compensation_semaines.py`
- Test: `backend/tests/unit/payroll/test_compensation_semaines.py`

**Interfaces:**
- `majorations(total: float, duree_hebdo: float) -> tuple[float, float]`
- `ecarts_par_semaine(planned_all, actual_all, fenetre: tuple[date, date]) -> dict[tuple[int, int], float]` (clé = (année ISO, semaine ISO), semaines dont le lundi est dans la fenêtre)
- `compenser(ecarts: Mapping[tuple[int,int], float], duree_hebdo) -> Compensation(semaines: tuple[BilanSemaine,...], net25, net50, solde_negatif)`
- `appliquer(evenements: list[dict], fenetre, compensation) -> list[dict]` (événements d'UN mois, avec `annee`/`mois`/`jour`)
- `mention(compensation) -> str`

- [x] **Step 1: Tests rouges** (fichier complet écrit à l'exécution : majorations, compensation juin, écarts journaliers Fuckar S28, application au calendrier, mention).
- [x] **Step 2: Vérifier le rouge** — `ModuleNotFoundError`.
- [x] **Step 3: Écrire le module.**
- [x] **Step 4: Vert + ruff.**

### Task 2: Le générateur applique l'option

**Files:**
- Modify: `backend/app/modules/payroll/documents/payslip_generator.py` (après `fenetre_variables = resoudre_fenetre_variables(...)`, avant l'écriture des `evenements_paie`)
- Test: `backend/tests/unit/payroll/test_compensation_semaines.py` (`appliquer_aux_mois` et `option_active`, testés sans Supabase ; le générateur n'a plus qu'un `if option_active(company_data)`)

- [x] Extraire l'orchestration en fonction pure dans le module de Task 1 (`appliquer_aux_mois`) ; le générateur ne fait que lire l'option et l'appeler ; résumé dans `saisies_data["compensation_semaines"]`.

### Task 3: Le bulletin porte la mention et le détail

**Files:**
- Modify: `backend/app/modules/payroll/documents/payslip_run_heures.py` (lit `saisie_du_mois["compensation_semaines"]`, le passe au moteur via `contexte`/argument), `backend/app/modules/payroll/engine/bulletin.py` (`payslip_data["compensation_semaines"]`), `backend/app/modules/payroll/documents/bulletin_view.py:432` (note comme `arbitrage_conges`)
- [x] Test: `backend/tests/unit/payroll/test_bulletin_view.py` (`TestNoteCompensationSemaines`) : la note apparaît avant le brut quand la mention est présente, pas de note sans mention, deux notes avec l'arbitrage CP.
- [x] Une régularisation antérieure (`is_regularisation_anterieure`) datée dans la fenêtre n'est jamais remplacée : elle appartient au bulletin, pas à une semaine.
- [x] Heures sup saisies à la main : le moteur les fait primer (`calcul_brut.py`, `declared_conj`) ; `avec_saisie_manuelle(resume, hs25, hs50)` (module pur, 4 tests) complète le résumé et la mention quand elles diffèrent des nets ; appelé par `engine/bulletin.py::_compensation_semaines_du_bulletin`.

### Task 4: Le réglage société

**Files:**
- [x] Modify: `backend/app/modules/companies/schemas/requests.py` (`compensation_heures_entre_semaines: Optional[bool]`), test `tests/unit/companies/test_settings_compensation_semaines.py` (delta vrai/faux/absent, chaîne refusée)
- [x] Create: `frontend/src/features/company/components/CompensationSemainesSettingsCard.tsx` (case à cocher, avertissement ambre, « Enregistrer » inactif tant que rien ne change), lecture dans `features/company/utils/compensationSemainesSettings.ts` (testée), branchée dans `CompanyPayrollTab.tsx` section « Organisation du temps & compte d'heures » ; `api/company.ts` type.

### Task 5: Recette, docs

- [x] Suite unitaire complète (6141 verts, un rouge d'environnement), vitest 592 verts, eslint, tsc (3 erreurs préexistantes hors périmètre).
- [ ] Contrôle réel en bac à sable : générer Cotte, Demory, Bugny, Fuckar juillet, option OFF puis ON (sans persister, `option_active` remplacé dans le module du générateur), lire HS/retenues.
- [ ] Passation §6, mémoire.
