# Architecture EYWAI

Document de référence pour l’organisation du dépôt. Détails backend : [backend/app/README.md](backend/app/README.md).

## Principes

- **Modular monolith** backend : API → application → domain → infrastructure.
- **Frontend** : `pages/` = coques de routes ; UI métier dans `features/` ou `components/<domain>/`.
- **DRY transverse** : `app/core/`, `app/shared/` (backend) ; `lib/queryKeys.ts` + `hooks/queries/` (frontend).
- **Multi-tenant** : résolution employé unique avec `company_id` via [`app/shared/employee_resolution.py`](backend/app/shared/employee_resolution.py).
- **Tests** : unit hermétiques (CI bloquante) ; intégration hors CI depuis le 26/09/2026.

## Frontend (`frontend/src/`)

```
pages/admin|rh|employee/   # lazy-loaded shells (App → lazyPages.ts)
features/<domain>/         # UI métier migrée depuis pages/*/tabs
components/<domain>/       # composants réutilisables existants
api/                       # clients HTTP
hooks/queries/             # React Query par domaine
lib/queryKeys.ts           # clés de cache centralisées
```

**Règles**

- `components/` et `hooks/` ne importent pas `@/pages/`.
- Pas de changement d’URL sans accord produit.
- Exports publics de [`app/lazyPages.ts`](frontend/src/app/lazyPages.ts) stables.

## Backend (`backend/app/`)

Voir [backend/app/README.md](backend/app/README.md). Garde-fous : `tests/unit/architecture/`.

## Programme de refonte

Phases 0–9 (garde-fous → resolve employee → HTTP deps → nettoyage front → features → god files → hubs → tests → gouvernance). ADRs : [`docs/decisions/adr/`](docs/decisions/adr/).

## CI

Source : [`.github/workflows/ci.yml`](.github/workflows/ci.yml), sur chaque push et chaque PR.

| Job | Étape | Bloquant |
|-----|-------|----------|
| Secrets | gitleaks | Oui |
| Backend | ruff | Non : informatif (`continue-on-error`) |
| Backend | import de l’app, `pytest tests/unit`, tests du scraping | Oui |
| Frontend | lint, `npm run test`, build, vérification des imports de pages | Oui |
| Frontend | contrôle de types (`npm run typecheck`) | Absent de la CI |
| Backend integration | `pytest tests/integration` | Coupé depuis le 26/09/2026 : il écrivait dans la base de test |

## PR checklist

- [ ] Couches respectées (pas de DB dans routers hors allowlist)
- [ ] Tests unitaires ajoutés ou mis à jour
- [ ] OpenAPI inchangé ou documenté
- [ ] Front : `npm run test` + snapshot routes OK
- [ ] Pas de `HTTPException` ajouté en couche application
