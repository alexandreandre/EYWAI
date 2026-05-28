# ADR 003 — Clés React Query centralisées

## Statut

Accepté (déploiement par domaine)

## Décision

Toutes les clés de cache passent par `frontend/src/lib/queryKeys.ts` ; hooks dans `hooks/queries/`.

## Migration

Domaines pilotes : employees, absences, formation — puis planning, payroll, recruitment.
