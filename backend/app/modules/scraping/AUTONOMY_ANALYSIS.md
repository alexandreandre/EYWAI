# Analyse d'autonomie — module scraping

## Étape A — Analyse des dépendances (état actuel)

### Imports externes au module (hors `app.modules.scraping.*`)

| Fichier | Import | Symbole(s) | Usage | Cible actuelle |
|---------|--------|------------|--------|----------------|
| `api/dependencies.py` | `app.core.database` | `supabase` | Requête table `super_admins` pour vérifier super admin | app/core/* (nouvelle archi) |
| `api/dependencies.py` | `app.core.security` | `get_current_user` | Dépendance FastAPI pour obtenir l'utilisateur connecté | app/core/* |
| `api/dependencies.py` | `app.modules.users.schemas.responses` | `User` | Type du paramètre `current_user` et accès à `current_user.id` | app/modules/* (contrat inter-module) |
| `api/router.py` | `app.core.security` | `get_current_user` | Dépendance sur routes protégées (ex. POST /execute) | app/core/* |
| `api/router.py` | `app.modules.users.schemas.responses` | `User` | Type `current_user` et passage de `current_user.id` aux commands | app/modules/* |
| `infrastructure/repository.py` | `app.core.database` | `supabase` | Toutes les opérations DB (tables scraping_*, RPC) | app/core/* |
| `infrastructure/scraper_runner.py` | `app.core.paths` | `SCRAPING_ROOT` | Résolution du chemin vers les scripts de scraping | app/core/* |

### Classification

- **app/core/*** : `database`, `security`, `paths` font partie du **socle transverse migré** (Phase 3). Ce n’est pas du legacy : `backend_api/core/` (legacy) n’est pas importé.
- **app.modules.users** : contrat inter-module (type `User` retourné par `get_current_user`). Accepté par les règles de placement pour un contrat métier inter-module.

### Imports legacy (hors app/*)

**Aucun.** Aucun fichier du module n’importe depuis :

- `api/*` (legacy)
- `schemas/*` (legacy racine)
- `services/*`
- `core/*` legacy (`backend_api/core/`)
- `backend_calculs/*`

### Dépendances à conserver (non legacy)

- **app.core.database.supabase** : accès DB unifié (nouvelle archi).
- **app.core.security.get_current_user** : authentification transverse (nouvelle archi).
- **app.core.paths.SCRAPING_ROOT** : chemin des scripts (défini dans app/core, nouvelle archi).
- **app.modules.users.schemas.responses.User** : type utilisateur connecté (contrat inter-module).

Aucun wrapper de compatibilité legacy n’est nécessaire : le module n’utilise que des éléments déjà sous `app/*`.

---

## Étape B — Modifications appliquées

Aucune modification de code n’a été nécessaire : le module ne contient aucun import legacy. Tous les imports pointent vers :

- `app.core.*`
- `app.modules.users.*` (contrat inter-module)
- `app.modules.scraping.*` (interne)
- bibliothèques externes (fastapi, pydantic, stdlib).

---

## Étape C — Vérification d’autonomie

1. **Aucun fichier dans `app/modules/scraping` n’importe** :  
   `api/*`, `schemas/*` (legacy), `services/*`, `core/*` legacy, ni aucun chemin legacy hors `app/*`.

2. **Les imports restants** pointent uniquement vers :  
   `app/core/*`, `app/modules/*`, et bibliothèques externes.

3. **Comportement** : aucune modification fonctionnelle ou de contrat HTTP n’a été effectuée.

---

## Sortie demandée

- **Imports legacy supprimés** : aucun (il n’y en avait pas).
- **Nouveaux fichiers créés ou complétés dans app/*** : aucun (hors ce fichier d’analyse).
- **Wrappers temporaires conservés** : aucun.
- **Verdict final** : **module autonome**.

Le module `app/modules/scraping` est structurellement autonome et indépendant du legacy : il ne dépend que du socle `app/core/*` et du contrat utilisateur `app.modules.users` (User), sans dépendance vers l’ancienne structure (api/*, core legacy, schemas/services legacy, backend_calculs).
