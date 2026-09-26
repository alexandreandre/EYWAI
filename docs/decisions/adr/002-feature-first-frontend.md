# ADR 002 — Frontend feature-first

## Statut

Accepté (migration progressive)

## Décision

- `pages/admin|rh|employee` : coques de routes lazy uniquement.
- `features/<domain>/` : UI métier (ex. `features/formation/components/tabs`).
- `components/` : UI générique et design system.

## Règle

`components/` et `hooks/` n'importent pas `@/pages/`.
