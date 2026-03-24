# Analyse d’autonomie — module recruitment

## Étape A — Imports legacy identifiés

Tous les fichiers sous `app/modules/recruitment` ont été passés en revue. Imports dirigés vers le legacy (hors `app/*`) :

| Fichier | Import legacy | Symbole(s) | Usage | Type | Cible correcte |
|--------|----------------|------------|--------|------|------------------|
| `api/router.py` | `from security import ...` | `User`, `get_current_user` | Auth et type utilisateur pour les routes (Depends, guards) | Sécurité / schéma utilisateur | `app.core.security` (get_current_user), `app.modules.users.schemas.responses` (User) |
| `infrastructure/repository.py` | `from core.config import ...` | `supabase` | Client Supabase pour toutes les opérations DB | Accès DB | `app.core.config` (réexporte depuis app.core.database) |
| `infrastructure/queries.py` | `from core.config import ...` | `supabase` | Client Supabase pour les requêtes lecture | Accès DB | `app.core.config` |

- `security` = `backend_api/security.py` (wrapper legacy qui réexporte depuis `app.core.security` et `app.modules.users.schemas.responses`).
- `core.config` = `backend_api/core/config.py` (config legacy ; la config cible est dans `app.core.config` / `app.core.database`).

Aucun import vers : `api/*`, `schemas/*` (racine), `services/*`, `backend_calculs/*`. Aucun autre fichier du module n’importe le legacy.

## Cibles dans la nouvelle architecture

- **Sécurité / auth** : `app.core.security.get_current_user` ; type `User` = `app.modules.users.schemas.responses.User` (contrat inter-module, déjà utilisé par `app.core.security`).
- **Accès DB (Supabase)** : `app.core.config` qui réexporte `supabase` depuis `app.core.database`.

Aucun nouveau fichier dans `app/shared/*` nécessaire : pas d’utilitaire ni schéma spécifique à créer ; le type `User` reste dans le module users (partagé par auth et tous les modules protégés).

## Wrappers temporaires conservés

Aucun dans `app/modules/recruitment`. Les wrappers `backend_api/security.py` et `backend_api/core/config.py` restent en place pour le reste du legacy ; le module recruitment ne les utilise plus.

## Modifications appliquées (étape B)

1. **api/router.py**  
   - Avant : `from security import User, get_current_user`  
   - Après : `from app.core.security import get_current_user` et `from app.modules.users.schemas.responses import User`

2. **infrastructure/repository.py**  
   - Avant : `from core.config import supabase`  
   - Après : `from app.core.config import supabase`

3. **infrastructure/queries.py**  
   - Avant : `from core.config import supabase`  
   - Après : `from app.core.config import supabase`

Aucun fichier créé dans `app/*` ; uniquement remplacement d’imports par leurs équivalents sous `app/*`.

## Vérification d’autonomie (étape C)

- Aucun fichier dans `app/modules/recruitment` n’importe : `api/*`, `schemas/*`, `services/*`, `core/*` (legacy), ni aucun chemin legacy hors `app/*`.
- Les seuls imports “externes” du module pointent vers : `app.core.*`, `app.modules.users.schemas.responses` (User), `app.modules.recruitment.*`, et bibliothèques (fastapi, pydantic, typing, etc.).
- Comportement HTTP et métier : inchangé (mêmes endpoints, méthodes, prefixes, paramètres, response models, logique d’auth et d’accès DB).

---

## Sortie attendue — résumé

**Imports legacy supprimés :**
- `api/router.py` : `from security import User, get_current_user`
- `infrastructure/repository.py` : `from core.config import supabase`
- `infrastructure/queries.py` : `from core.config import supabase`

**Nouveaux fichiers créés ou complétés dans app/* :**  
Aucun. Uniquement remplacement d’imports par des cibles déjà présentes sous `app/*`.

**Wrappers temporaires conservés dans le module :**  
Aucun.

**Verdict final : module autonome.**  
Le module recruitment est structurellement autonome et indépendant du legacy ; il ne dépend que de `app/*` (`app.core`, `app.modules.users` pour le type `User`, `app.modules.recruitment`). Aucun import vers `api/*`, `schemas/*`, `services/*`, `core/*` legacy ni hors `app/*`.
