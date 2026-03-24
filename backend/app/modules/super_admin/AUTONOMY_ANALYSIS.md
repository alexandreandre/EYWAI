# Analyse d’autonomie – module super_admin

## 1. Imports dirigés vers l’extérieur du module

Recensement de tous les imports **hors** `app.modules.super_admin.*` dans le module.

| Fichier | Import | Symbole(s) | Usage | Type |
|---------|--------|------------|--------|------|
| **api/router.py** | app.core.security | get_current_user | Dépendance FastAPI pour l’auth | Sécurité transverse (app) |
| **api/router.py** | app.modules.users.schemas.responses | User | Type du paramètre `current_user` (Depends(get_current_user)) ; seul `.id` est utilisé | Schéma autre module |
| **schemas/requests.py** | app.modules.companies.schemas.requests | CompanyCreate, CompanyCreateWithAdmin, CompanyUpdate | Body des routes POST/PATCH companies | Schéma autre module |
| **infrastructure/repository.py** | app.core.database | get_supabase_client | Client Supabase table super_admins | Accès DB (app core) |
| **infrastructure/queries.py** | app.core.database | get_supabase_client, get_supabase_admin_client | Requêtes Supabase + Auth admin | Accès DB (app core) |
| **infrastructure/commands.py** | app.core.database | get_supabase_client | Commandes Supabase | Accès DB (app core) |
| **infrastructure/providers.py** | app.core.database | get_supabase_admin_client | Auth admin (create_user, get_user_by_id, etc.) | Accès DB (app core) |

Aucun import vers : `api/*`, `schemas/*` (racine), `services/*`, `core/*` (racine), `backend_calculs/*`, ni aucun chemin hors `app/*`.

---

## 2. Cibles pour autonomie

- **app.core.*** (database, security) : **conservés**. Transverse, partie de la nouvelle architecture.
- **app.modules.users (User)** : **supprimer** la dépendance en ne typant plus avec `User`. Utiliser un **Protocol** local exigeant uniquement `id` (str ou UUID), le router reste branché sur `Depends(get_current_user)` sans importer le type `User`.
- **app.modules.companies (CompanyCreate, CompanyCreateWithAdmin, CompanyUpdate)** : **supprimer** la dépendance en **recopiant** les trois définitions dans `app/modules/super_admin/schemas/requests.py`, à l’identique (champs, types, optionnels), pour garder le même contrat HTTP sans importer le module companies.

---

## 3. Wrappers temporaires conservés

Aucun. Aucun wrapper de compatibilité legacy n’est utilisé dans le module ; les seules dépendances externes sont `app.core` (autorisé) et les deux modules ci‑dessus, qui sont éliminées par les changements ci‑dessus.

---

## 4. Modifications prévues (minimales)

1. **schemas/requests.py**  
   - Ajouter les définitions locales de `CompanyCreate`, `CompanyCreateWithAdmin`, `CompanyUpdate` (copie stricte depuis `app.modules.companies.schemas.requests`).  
   - Supprimer l’import depuis `app.modules.companies.schemas.requests`.

2. **api/router.py**  
   - Introduire un `Protocol` local (ex. `CurrentUserProtocol`) avec attribut `id`.  
   - Typer le paramètre de `verify_super_admin` avec ce Protocol au lieu de `User`.  
   - Supprimer l’import de `User` depuis `app.modules.users.schemas.responses`.

Aucun changement d’endpoints, méthodes HTTP, préfixes, paramètres, réponses, codes de statut ni logique métier.

---

## 5. Vérification d’autonomie (après modifications)

- **Aucun fichier** dans `app/modules/super_admin` n’importe : `api/*`, `schemas/*` (racine), `services/*`, `core/*` (racine), `backend_calculs/*`, ni `app.modules.users`, ni `app.modules.companies`.
- **Imports restants hors module** : uniquement `app.core.database` (get_supabase_client, get_supabase_admin_client) et `app.core.security` (get_current_user), plus bibliothèques externes (fastapi, pydantic, stdlib).
- **Comportement** : contrats des schémas CompanyCreate / CompanyCreateWithAdmin / CompanyUpdate identiques (définitions recopiées) ; typage du current_user par Protocol local, seul `current_user.id` est utilisé → pas de changement fonctionnel ni HTTP.

---

## 6. Verdict final

**Module autonome.**

- Aucun wrapper temporaire conservé.
- Dépendances externes limitées à `app.core.*` (transverse) et librairies.
- Aucune dépendance legacy hors `app/*` ; plus de dépendance à `app.modules.users` ni `app.modules.companies`.
