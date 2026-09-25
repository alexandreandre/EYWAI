# La CI tourne sur toutes les branches

Décidé le 24/09/2026 avec Alexandre.

## Pourquoi

`ci.yml` ne se lançait que sur les PR et les push sur `main`. La branche
`fix/payslip-edit-state` a porté plus de 70 commits, déployés sur le test, sans
qu'aucune CI ne les contrôle : les seuls tests passés étaient ceux lancés à la
main en local.

## Ce qui change

- `on.push.branches: ["**"]` : chaque push, sur n'importe quelle branche, lance
  la recherche de secrets, le backend (tests unitaires, chargement de
  l'application, OpenAPI) et le frontend (lint, tests, build).
- `backend-integration` porte `if: github.event_name == 'pull_request' ||
  github.ref == 'refs/heads/main'` : il ne tourne que là où il tournait déjà.
  Ces tests écrivent dans la base de TEST, où Colorplast fait sa vraie paie.

## Ce qui ne change pas

- `deploy.yml` suit `workflow_run` de la CI avec `branches: [main]` : une CI
  réussie sur une branche ne déclenche aucun déploiement.
- Les étapes et leur caractère bloquant (ruff reste informatif).

## Conséquences acceptées

- Une branche avec une PR ouverte fait tourner la CI deux fois (push et PR).
- La CI tourne en Python 3.11, comme l'image de production, alors que le
  développement local est en 3.12 : un code propre à 3.12 casse désormais la CI
  de la branche au lieu de casser la production.

## Vérification

Après le push : la CI tourne sur la branche (secrets, backend, frontend verts ;
intégration ignorée) et aucun déploiement ne part.
