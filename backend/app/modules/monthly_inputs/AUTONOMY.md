# Autonomie du module monthly_inputs

## Étape A — Analyse des dépendances (état actuel)

### Imports externes au module (hors `app.modules.monthly_inputs.*`)

| Fichier | Import | Symbole | Usage | Cible actuelle |
|---------|--------|---------|--------|----------------|
| `infrastructure/repository.py` | `app.core.database` | `supabase` | Client Supabase pour table `monthly_inputs` | **app/core/** (nouvelle architecture) |
| `infrastructure/queries.py` | `app.core.database` | `supabase` | Client Supabase pour table `payroll_config` (primes) | **app/core/** (nouvelle architecture) |

### Imports legacy (api/*, schemas/*, services/*, core/* legacy, hors app/*)

**Aucun.** Le module n’importe ni `api/*`, ni `schemas/*`, ni `services/*`, ni `backend_api/core` (legacy).  
La seule dépendance externe au module est `app.core.database` (Supabase), qui fait partie de `app/*`.

### Dépendances internes

- **api/** → application, schemas (requests, responses)
- **application/** → domain (implicite via infra), infrastructure (repository, queries), schemas (requests), dto
- **domain/** → stdlib uniquement
- **infrastructure/** → app.core.database, domain (interfaces), domain (entities pour mappers)
- **schemas/** → pydantic, stdlib

Aucun cycle d’import. Aucun wrapper de compatibilité legacy dans le module.

---

## Étape B — Modifications appliquées

- **Imports legacy supprimés :** aucun (le module n’en avait pas).
- **Nouveaux fichiers créés dans app/* :** aucun (déjà conforme).
- **Wrappers temporaires conservés :** aucun.

---

## Étape C — Vérification d’autonomie

1. Aucun fichier dans `app/modules/monthly_inputs` n’importe : `api/*`, `schemas/*`, `services/*`, `core/*` legacy, ni aucun chemin hors `app/*` (à l’exception de `app.core.database` et des librairies externes).
2. Les seuls imports “externes” au module pointent vers : **app.core.database** (Supabase), **fastapi**, **pydantic**, et la stdlib.
3. Comportement HTTP et métier inchangé ; aucun endpoint, méthode, path, body ou réponse modifié.

---

## Verdict

**Module autonome.**

Le module est structurellement autonome et indépendant du legacy. Il ne dépend que de `app.core.database` pour l’accès Supabase, dans le périmètre `app/*` de la nouvelle architecture.
