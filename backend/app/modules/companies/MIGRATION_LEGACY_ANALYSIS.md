# Étape A — Analyse des dépendances legacy (module companies)

## 1. Imports legacy identifiés

| Fichier | Import legacy | Symbole(s) | Usage | Type |
|---------|----------------|------------|--------|------|
| `api/router.py` | `security` | `User`, `get_current_user` | Dépendance FastAPI (Depends) et type du current_user | Sécurité / Auth |
| `infrastructure/repository.py` | `core.config` (fallback) | `supabase` | Client DB pour table companies | Accès DB |
| `infrastructure/queries.py` | `core.config` (fallback) | `supabase` | Client DB pour companies, employees, payslips, profiles | Accès DB |

## 2. Détail par import

### 2.1 `from security import User, get_current_user` (api/router.py)
- **Fichier exact legacy :** `security` (racine backend_api) → réexporte depuis `app.core.security` et `schemas.user`.
- **Pourquoi utilisé :** injection du user connecté et typage (User) pour les 3 endpoints.
- **Cible correcte :**
  - `get_current_user` → `app.core.security` (déjà dans app/*).
  - `User` → type métier partagé ; canonique dans `app.modules.users.schemas.responses.User` (schéma déjà migré). Contrat inter-module (utilisateur authentifié).

### 2.2 `from core.config import supabase` (repository.py, queries.py)
- **Fichier exact legacy :** `core.config` = backend_api/core/config.py (client Supabase racine).
- **Pourquoi utilisé :** fallback si `app.core.database` indisponible (contexte legacy).
- **Cible correcte :** `app.core.database.supabase` uniquement. Pas de wrapper legacy nécessaire pour autonomie du module dans la nouvelle architecture.

## 3. Cibles dans la nouvelle architecture

- **Sécurité / User :** `app.core.security.get_current_user` ; `app.modules.users.schemas.responses.User` (contrat inter-module).
- **DB :** `app.core.database.supabase` (suppression du fallback `core.config`).

## 4. Wrappers temporaires conservés

Aucun. Le module peut être rendu autonome sans wrapper :
- Le routeur n’a pas besoin de `security` (racine) s’il importe depuis `app.core.security` et `app.modules.users.schemas.responses`.
- L’infrastructure n’a pas besoin du fallback `core.config` pour fonctionner sous la nouvelle architecture (point d’entrée `app.main:app` utilise `app.core.database`).

---

# Étape B — Modifications appliquées

1. **api/router.py**  
   - Supprimé : `from security import User, get_current_user`  
   - Ajouté : `from app.core.security import get_current_user` ; `from app.modules.users.schemas.responses import User`

2. **infrastructure/repository.py**  
   - Supprimé : try/except avec fallback `from core.config import supabase`  
   - Utilisation unique : `from app.core.database import supabase`

3. **infrastructure/queries.py**  
   - Supprimé : try/except avec fallback `from core.config import supabase`  
   - Utilisation unique : `from app.core.database import supabase`

Aucun nouveau fichier créé dans app/shared/* : le type `User` est déjà défini dans `app.modules.users.schemas.responses` (contrat inter-module).

---

# Étape C — Vérification d’autonomie

- Aucun fichier dans `app/modules/companies` n’importe désormais : `api/*`, `schemas/*`, `services/*`, `core.config` (legacy), ni aucun chemin legacy hors `app/*`.
- Imports restants : `app.core.*`, `app.modules.companies.*`, `app.modules.users.schemas.responses` (User), et bibliothèques (fastapi, pydantic, typing, etc.).
- Comportement HTTP et métier inchangé : mêmes endpoints, méthodes, prefixes, paramètres, response models, codes de statut, auth et guards.

**Verdict final : module autonome.**  
Aucun wrapper temporaire conservé.
