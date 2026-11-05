# Dispense de mutuelle — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** permettre à la RH de poser une dispense de mutuelle sur la fiche ; l'alerte DSN « mutuelle absente » se tait pour une dispense valable et dit quoi faire sinon.

**Architecture:** une fonction pure côté serveur (`shared/domain/dispense_mutuelle.py`) juge la mutuelle du mois et renvoie la phrase d'alerte ou `None` ; `check_dsn_data` l'appelle. Côté écran, un module `dispenseMutuelle.ts` porte les 7 motifs et la conversion fiche ↔ formulaire, un composant `DispenseMutuelleFields` s'affiche sous la formule de mutuelle.

**Tech Stack:** Python 3 / pytest (backend), React + react-hook-form + zod / vitest (frontend).

Spec : `docs/superpowers/specs/2026-11-05-dispense-mutuelle-design.md`.

## Global Constraints

- Aucun nom de salarié réel dans le code, les tests ou les commits (dépôt public).
- Données : `specificites_paie.mutuelle.dispense = {motif, demande_recue_le, justificatif_recu_le, fin_le}` (dates `AAAA-MM-JJ`), `null` quand une formule est choisie.
- Codes des motifs : `couverture_collective`, `css`, `assurance_individuelle`, `cdd_moins_12_mois`, `cdd_12_mois_et_plus`, `temps_partiel_10_pourcent`, `anterieur_decision_unilaterale`.
- Périmètre du contrôle inchangé : CDI et CDD seulement ; l'alerte « prévoyance absente » ne bouge pas.
- Tests backend : `APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key /Users/alex/dev/EYWAI/backend/.venv/bin/python -m pytest <chemin>` depuis `backend/`.

---

### Task 1 : le contrôle côté serveur

**Files:**
- Create: `backend/app/shared/domain/dispense_mutuelle.py`
- Create: `backend/tests/unit/shared/test_dispense_mutuelle.py`
- Modify: `backend/app/modules/exports/infrastructure/export_dsn.py` (bloc « mutuelle absente », ~l. 653)
- Modify: `backend/tests/unit/exports/test_dsn_avertissements_mutuelle.py`

**Interfaces:**
- Produces: `alerte_mutuelle(mutuelle: Any, contract_type: str | None, annee: int, mois: int) -> str | None` ; `MOTIFS_DISPENSE: dict[str, str]`.

- [ ] Écrire les tests du domaine (un par ligne du tableau de la spec, plus adhésion et contrat hors périmètre), les voir échouer.
- [ ] Écrire `dispense_mutuelle.py` (docstring sourcée : D911-2, R242-1-6, D911-5, lus le 05/11/2026).
- [ ] Brancher dans `check_dsn_data` : `alerte = alerte_mutuelle(mutuelle, contract_type, annee_dsn, mois_dsn)` puis `warnings.append(f"Salarié {employee_name} : {alerte}")`.
- [ ] Ajouter à `test_dsn_avertissements_mutuelle.py` : dispense valable → plus d'alerte mutuelle, l'alerte prévoyance reste.
- [ ] Lancer `tests/unit/shared/test_dispense_mutuelle.py tests/unit/exports/` : vert. Commit.

### Task 2 : la fiche côté écran

**Files:**
- Create: `frontend/src/features/employee-detail/components/dispenseMutuelle.ts` (+ `dispenseMutuelle.test.ts`)
- Create: `frontend/src/features/employee-detail/components/DispenseMutuelleFields.tsx`
- Modify: `employeeProfileEditSchema.ts` (champ `mutuelle.dispense`, contrôle dans `superRefine`)
- Modify: `employeeProfileFormUtils.ts` (`buildDefaultValues`, `buildUpdatePayload`)
- Modify: `EmployeeProfileEditForm.tsx` (rendu sous la formule)
- Modify: `types.ts` (type du bloc mutuelle)
- Modify: `employeeProfileFormUtils.test.ts`

**Interfaces:**
- Produces: `MOTIFS_DISPENSE_MUTUELLE: MotifDispense[]` (`{code, libelle, source, besoin: 'justificatif' | 'fin' | null, selonActe: boolean}`) ; `dispenseVersFormulaire(d: unknown): DispenseFormulaire` ; `dispenseVersFiche(f: DispenseFormulaire, aUneFormule: boolean): DispenseFiche | null` ; `problemesDispense(f: DispenseFormulaire): {champ: keyof DispenseFormulaire, message: string}[]`.

- [ ] Tests vitest de `dispenseMutuelle.ts` (aller-retour, effacement si formule, problèmes par motif), les voir échouer, implémenter.
- [ ] Schéma : `dispense: z.object({active, motif, demande_recue_le, justificatif_recu_le, fin_le})` ; `superRefine` ajoute les problèmes seulement si aucune formule n'est choisie et que `active` est vrai (un champ caché ne doit jamais bloquer l'enregistrement en silence).
- [ ] `buildDefaultValues` lit la dispense ; `buildUpdatePayload` écrit `dispense: dispenseVersFiche(...)`.
- [ ] Tests `employeeProfileFormUtils.test.ts` : la dispense part dans l'enregistrement, devient `null` avec une formule, le schéma refuse une dispense sans date de demande et accepte une formule sans dispense.
- [ ] Composant `DispenseMutuelleFields` (case, motif, dates selon le motif, deux lignes d'aide), rendu sous la formule quand aucune n'est choisie.
- [ ] `npx vitest run src/features/employee-detail` puis `npx tsc --noEmit -p .` : vert. Commit.

### Task 3 : en ligne et recette

- [ ] Suite backend complète et vitest complet ; pousser `feat/dispense-mutuelle` ; CI verte.
- [ ] `gh workflow run deploy-test-env.yml --ref feat/dispense-mutuelle` (sans migration), suivre par `gh run view`, contrôler `/health`.
- [ ] Recette en mode paie sur le site de test, sur une fiche de test : poser une dispense « conjoint », voir l'alerte quitter l'aperçu DSN, la voir revenir avec un justificatif de plus d'un an, remettre la fiche en état.
- [ ] Changelog et mémoire.
