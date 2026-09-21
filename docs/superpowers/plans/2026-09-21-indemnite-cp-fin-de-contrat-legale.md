# Indemnité de CP de fin de contrat, règle légale par période : plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retirer l'option « salaire rétabli » et calculer l'indemnité de CP de fin de CDD/mission par période de référence, sur les jours restants, dixième contre maintien ; Demory juillet → 766,39.

**Architecture:** Module pur `engine/iccp_fin_contrat.py` ; `_calculer_iccp_cdd` l'appelle quand le run a posé `contexte.cp_fin_de_contrat`, repli sur le dixième global sinon ; mention sur le bulletin.

**Tech Stack:** Python 3.12 / pytest / ruff (`backend/.venv/bin/python`) ; React + TypeScript + vitest + eslint.

Spec : `docs/superpowers/specs/2026-09-21-indemnite-cp-fin-de-contrat-legale-design.md`.

## Global Constraints

- Sans compteurs, aucun montant ne change (tests existants intacts).
- Aucun commit sans demande explicite d'Alexandre.

---

### Task 1: Retirer l'option « salaire rétabli, congés N-1 inclus »
- [x] Backend : `engine/iccp_fin_cdd.py` supprimé, `calcul_brut` (branche, imports), `payslip_run_heures` (solde N-1), `payslip_generator` (paramètre), `engine/bulletin` + `bulletin_view` (détail/note), `CompanySettingsUpdate.indemnite_cp_fin_cdd`, tests correspondants.
- [x] Front : carte, utilitaire et test, montage, type API.
- [x] Suites vertes.

### Task 2: Module pur `iccp_fin_contrat`
- [x] Tests rouges : Demory par période (306,78 / 459,61 / 766,39), maintien plus favorable, période sans restants, brut inconnu → maintien seul, mention.
- [x] Module, vert, ruff.

### Task 3: Moteur et run
- [x] `_calculer_iccp_cdd` : calcul légal si `contexte.cp_fin_de_contrat`, repli sinon ; détail sur le contexte (tests `test_cdd_cp_sortie`).
- [x] `payslip_run_heures.cp_fin_de_contrat` + `periodes_depuis_compteurs` (pure, testée) ; lecture de la rémunération de la période précédente.
- [x] Bulletin : `indemnite_cp_fin_contrat`, note (tests).

### Task 4: Recette, docs
- [x] Bac à sable Demory → 766,39 (brut 3 336,07) ; suites vertes (backend 6180+, vitest 596) ; génération réelle de Demory sur le test après déploiement.
- [x] Passation (§9 réécrit, chantier §4 clos), mémoire.
