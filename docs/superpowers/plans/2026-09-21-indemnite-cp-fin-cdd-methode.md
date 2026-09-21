# Indemnité de CP de fin de CDD, méthode au choix : plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un réglage société à deux méthodes pour l'indemnité de CP de fin de CDD ; la méthode « salaire rétabli, solde N-1 inclus » redonne Quadra au centime sur Demory (940,23).

**Architecture:** Module pur `engine/iccp_fin_cdd.py` ; `_calculer_iccp_cdd` choisit l'assiette ; le run lit le solde N-1 ; mention sur le bulletin ; réglage + carte front.

**Tech Stack:** Python 3.12 / pytest / ruff (`backend/.venv/bin/python`) ; React + TypeScript + vitest + eslint.

Spec : `docs/superpowers/specs/2026-09-21-indemnite-cp-fin-cdd-methode-design.md`.

## Global Constraints

- Méthode par défaut : aucun montant ne change (tests existants intacts).
- Aucun commit sans demande explicite d'Alexandre.
- Les rouges d'environnement ne comptent pas.

---

### Task 1: Module pur `iccp_fin_cdd`
- [x] Tests rouges (`tests/unit/payroll/test_iccp_fin_cdd.py`, 15 tests) : méthode, salaire rétabli, valeur jour, assiette Demory, mention.
- [x] Module `engine/iccp_fin_cdd.py`, vert, ruff.

### Task 2: Moteur
- [x] `_calculer_iccp_cdd` : assiette selon la méthode, détail sur `contexte.detail_iccp_fin_cdd` ; `test_cdd_cp_sortie.py` : contexte façon Demory (base hors HS structurelles, 39 h, sortie le 24/07) → 1 772,64 / 797,04 / 940,23 ; défaut 876,74 sans détail ; sortie en fin de mois sans solde N-1.
- [x] `payslip_run_heures.solde_cp_n_1_pour_l_indemnite_de_fin_de_cdd` : requête du pied de page seulement quand la méthode est active et que c'est le dernier mois d'un CDD ; sinon 0 sans requête.
- [x] Générateur : `parametres_paie.indemnite_cp_fin_cdd` depuis `companies.settings`.

### Task 3: Bulletin
- [x] `engine/bulletin.detail_indemnite_cp_fin_cdd` → `bulletin["indemnite_cp_fin_cdd"]` ; `bulletin_view` : note avant le brut (tests).

### Task 4: Réglage
- [x] `CompanySettingsUpdate.indemnite_cp_fin_cdd` Literal (5 tests, valeur inconnue refusée) ; front : `IndemniteCpFinCddMethode` dans `api/company.ts`, carte `IndemniteCpFinCddSettingsCard` (RadioGroup, section « Jours fériés & congés »), `utils/indemniteCpFinCddSettings.ts` testé.

### Task 5: Recette, docs
- [x] Suites (backend 6179 verts, vitest 595, eslint, tsc hors 3 erreurs préexistantes) ; bac à sable Demory méthode forcée → 940,23, brut 3 509,91, net imposable 2 679,30, net social 2 785,59 = Quadra ; défaut → 876,74 inchangé.
- [x] Passation §9, mémoire.
