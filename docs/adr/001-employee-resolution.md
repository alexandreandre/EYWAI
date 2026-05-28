# ADR 001 — Résolution employé unique

## Statut

Accepté

## Contexte

Plusieurs modules résolvaient `employees.id` avec des requêtes Supabase divergentes, parfois sans `company_id`.

## Décision

Point d'entrée unique : `app.shared.employee_resolution.resolve_employee_id_for_user_account`, implémenté dans `employees.infrastructure.queries`.

## Conséquences

- Wrappers métier autorisés dans `absences.application.service`, `expenses`, `saisies_avances`.
- Tests architecture `test_employee_resolution_guard.py` empêchent les réimplémentations.
