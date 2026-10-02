# Plan — demandes Gaëlle

Spec : `docs/superpowers/specs/2026-10-01-demandes-gaelle.md`.

Pas de déploiement, pas de commit. Migration appliquée seulement sur la base de test `tlvkjwleahkmuzcegrde`.

## 1. Congé sans solde

- `absence_calendar.py` : `sans_solde` → `absence_non_remuneree`, et ce type dans `ABSENCE_CALENDAR_TYPES`.
- `ecart_rules.py` : retirer `sans_solde` de `_TYPES_DEMANDE_SANS_CALENDRIER`. Le JTC y reste.
- `analyzer.py` : garder un événement `absence_non_remuneree` même à 0 h.
- `AbsenceRequestModal.tsx` : choix « Congé sans solde » dans la liste RH.
- `schedulesAbsenceConflict.ts` : même règle, et `absence_non_remuneree` n’est pas un conflit.
- Tests : `test_ecart_rules.py`, `schedulesAbsenceConflict.test.ts`, analyzer.

## 2. École

- `calendarTypes.ts` : libellé, couleurs, légende, sélecteur, exclu de la copie de mois.
- `payslip_run_heures.py` : `ecole` dans les jours couverts.
- Test : un jour École à 0 h ne produit pas d’événement ; `_est_une_absence("ecole")` est faux.

## 3. Brut

- `frontend/src/lib/brutDureeHebdo.ts` + test.
- Affiché sous le salaire de base dans `CreateEmployeeForm` et `EmployeeProfileEditForm`.

## 4. Contrats

- Migration `employee_contract_periods` (RLS comme les profils BOETH).
- `GET/POST/DELETE /api/employees/{id}/contract-periods`, réservé RH.
- Carte sur la fiche. Le contrat en cours vient de la fiche. Les lignes ajoutées sont les contrats passés.
