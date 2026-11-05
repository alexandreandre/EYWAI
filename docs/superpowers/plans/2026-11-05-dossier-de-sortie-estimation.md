# Dossier de sortie : estimation légale — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** le dossier de départ d'un CDD estime la prime et les congés selon la loi (spec `docs/superpowers/specs/2026-11-05-dossier-de-sortie-estimation-design.md`, règles R1 à R8), et le bulletin de sortie d'un départ en juin lit la bonne période.

**Architecture :** une lecture unique des bruts du contrat (`bruts_du_contrat`, `reference_remuneration.py`) sert la prime, le repli et le brut « avant le mois » du dossier ; une fonction `remuneration_des_periodes` (`payslip_run_heures.py`) aligne les cumuls du mois précédent sur la période des compteurs, pour le bulletin et le dossier ; les compteurs savent se lire « sans la reprise » pour un départ payé par l'ancien logiciel.

**Tech Stack :** Python 3.11 (CI), pytest ; React + TypeScript, vitest.

## Global Constraints

- Aucun nom de salarié dans un commit, un test ou un document commité.
- Aucun bulletin régénéré ; aucune écriture en base hors du script « lance ».
- Toute phrase à l'écran dit ce que Martine a fait (jamais d'état silencieux).
- Tests backend : `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest <chemin> -q` depuis `backend/`.
- Le bulletin ne change que pour un départ au premier mois d'une période de congés : filet avant/après (`~/dev/eywai-filet/lancer.sh`, `comparer5.py`), zéro écart attendu.

---

### Tâche 1 : R4 — période des cumuls alignée sur les compteurs (bulletin et dossier)

**Files :** Modify `backend/app/modules/payroll/documents/payslip_run_heures.py` (`cp_fin_de_contrat`), `backend/app/modules/payroll/engine/calcul_indemnites_sortie.py` (`_conges_par_periode_a_la_sortie`) ; Test `backend/tests/unit/payroll/test_remuneration_des_periodes.py`.

**Produces :** `remuneration_des_periodes(employee_id: str, cumuls: dict | None, compteurs: dict | None) -> tuple[float | None, float | None]` = (brut de la période précédente, brut de la période en cours avant le mois). Le second vaut `None` quand les cumuls ne disent rien de la période en cours (pas de `brut_reference_period_start`).

- [ ] Test rouge : départ en juin, cumuls de mai (`brut_reference_period_start` 2025-06-01, `brut_reference_n_1` 36 000), compteurs « 01/06/2026 – 31/05/2027 » → (36 000 lu sur le cumul de mai via `_brut_de_la_periode_precedente`, 0.0). Départ en octobre, cumuls de septembre de la période en cours → inchangé (précédente lue comme avant, avant le mois = `brut_reference_n_1`). Cumuls sans période → (None, None).
- [ ] Implémenter : lire le début de la période en cours dans `compteurs["conges_payes"]["periode"]` ; si le début des cumuls est antérieur, rappeler `_brut_de_la_periode_precedente` avec `{"cumuls": {"brut_reference_period_start": <début en cours>}}` et rendre 0.0.
- [ ] Brancher `cp_fin_de_contrat` (None → 0.0, comportement d'avant) et le dossier.
- [ ] Vert, commit `fix(conges): un départ en juin lit la période close dans les cumuls de mai`.

### Tâche 2 : R1, R2, R5 — `bruts_du_contrat` et le dossier

**Files :** Modify `backend/app/modules/payroll/engine/reference_remuneration.py`, `calcul_indemnites_sortie.py` ; Test `backend/tests/unit/payroll/test_bruts_du_contrat.py`.

**Produces :** `bruts_du_contrat(employee_id, depuis: date, jusqu_au: date, supabase_client, *, salaire: float, estimer_le_dernier_mois: bool) -> tuple[float, int, list[str]]` = (total, mois lus sur un bulletin, alertes). Mois de `depuis` à `jusqu_au` ; dernier mois estimé au salaire × jours sous contrat / jours du mois quand `estimer_le_dernier_mois` ; mois sans bulletin = salaire au prorata des jours sous contrat, alerte « Bulletin MM/AAAA absent — salaire du contrat utilisé. » ; lecture en échec : « Bulletin MM/AAAA illisible — salaire du contrat utilisé. ».

- [ ] Tests rouges : contrat 29/06-30/09, bulletins juin 272,73 / juillet / août 3 000 / septembre 5 782,59, salaire 3 000 → estimé : 9 272,73 (septembre jamais lu). Sans bulletin de juin : 200,00 (2/30 × 3 000) et une alerte. Lecture qui lève → alerte « illisible ».
- [ ] `lire_brut_total_contrat` et `lire_bruts_periode_reference` délèguent : la seconde prend `entree` et `sortie` et borne la période (R1).
- [ ] Dossier : la prime se calcule sur `bruts_du_contrat(entrée, sortie, estimé)` (R2) ; le repli passe `entree`/`sortie` (R1) ; quand `remuneration_des_periodes` rend `None` pour la période en cours, le brut avant le mois = `bruts_du_contrat(max(début de période, entrée), fin du mois précédent, non estimé)` (R5).
- [ ] R3 : la prime n'entre dans la base des congés que pour `fin_cdd` / `fin_mission`.
- [ ] Vert (dont `test_iccp_sortie.py`, `test_reference_remuneration.py`), commit.

### Tâche 3 : R6 — départ payé par l'ancien logiciel

**Files :** Modify `backend/app/modules/absences/application/queries.py` (`get_absence_balances_for_payslip`, paramètre `sans_la_reprise: bool = False`), `backend/app/modules/absences/infrastructure/repository.py` (`list_validated_for_employees(..., avec_coupure_de_reprise=True)`), `calcul_indemnites_sortie.py` ; Test `backend/tests/unit/payroll/test_dossier_depart_avant_reprise.py`.

- [ ] Test rouge : reprise datée du 30/09 (ouverture −6,38), départ au 30/09 → le dossier lit les compteurs `sans_la_reprise=True` et porte l'alerte « Départ payé par l'ancien logiciel… ». Départ au 31/10 → compteurs avec la reprise, sans alerte.
- [ ] Implémenter : `sans_la_reprise` saute `_reprise_posterieure_au_bulletin`, prend un ajustement vide et le planning sans coupure.
- [ ] Vert, commit.

### Tâche 4 : R7 — reprise à un seul prorata

**Files :** Modify `backend/app/modules/absences/application/leave_settings_commands.py` (`apply_cp_solde_import`) ; Test `backend/tests/unit/absences/test_reprise_prorata_mois_entree.py`.

- [ ] Test rouge : entrée 29/06, reprise au 30/09 à solde 0, recalage sans compteur → ouverture N −8,33 (et non −6,38).
- [ ] Implémenter : l'acquis théorique se calcule avec `dataclasses.replace(EmployeeLeaveAdjustment.empty(), cp_opening_reference_date=ref)`.
- [ ] Vert, commit.

### Tâche 5 : R8 — « Fin de CDD » proposée

**Files :** Modify `backend/app/modules/employee_exits/application/queries.py` (`contract_type`, `contract_end_date` dans la liste), `frontend/src/api/employeeExits.ts` (`SimpleEmployee`), `frontend/src/components/exits/CreateExitDialog.tsx` ; Create `frontend/src/features/employee-exits/utils/motifPropose.ts` + `.test.ts`.

**Produces :** `motifProposeAuDepart(salarie?: { contract_type?: string | null; contract_end_date?: string | null }) : { motif: 'fin_cdd'; dernierJour: string; phrase: string } | null`.

- [ ] Tests rouges vitest : CDD + fin 2026-09-30 → fin_cdd, « Proposé par Martine : CDD qui finit le 30/09/2026. » ; CDI → null ; CDD sans fin → null.
- [ ] Formulaire : au choix du salarié, si la RH n'a pas encore choisi de motif (réf. `motifChoisiParLaRh`) et qu'aucun motif n'est imposé, poser le motif et le dernier jour (s'il est vide) ; afficher la phrase sous le motif tant qu'il vaut « Fin de CDD ».
- [ ] Test backend de la liste ; vert ; commit.

### Tâche 6 : vérification, filet, données

- [ ] Suite unitaire backend complète, frontend `npm run lint && npm test -- --run`.
- [ ] Filet avant/après sur le commit de base et le commit final : 0 écart.
- [ ] Recalcul du dossier en lecture seule (script du scratchpad) : chiffres « après » de la spec vérifiés ou corrigés.
- [ ] `~/dev/eywai-filet/dossier-sortie-2026-11-05/simuler.sh` puis `appliquer.sh` (motif du dossier, ouverture −8,33), en attente de « lance ».
- [ ] Code review, fusion dans `feat/dsn-octobre`, CHANGELOG, déploiement, mémoire.
