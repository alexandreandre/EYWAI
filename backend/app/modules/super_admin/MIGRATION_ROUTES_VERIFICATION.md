# Vérification exhaustive des routes – module super_admin

Comparaison stricte entre le routeur legacy (`api/routers/super_admin.py`) et le nouveau routeur (`app/modules/super_admin/api/router.py`).

---

## 1. Liste des routes legacy

| # | Méthode | Chemin complet | Query params | Path params | Body | Dépendance | Codes HTTP |
|---|--------|----------------|--------------|-------------|------|------------|------------|
| 1 | GET | `/api/super-admin/dashboard/stats` | — | — | — | `verify_super_admin` | 200, 403, 500 |
| 2 | GET | `/api/super-admin/companies` | `skip`, `limit`, `search`, `is_active` | — | — | `verify_super_admin` | 200, 403, 500 |
| 3 | GET | `/api/super-admin/companies/{company_id}` | — | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 4 | POST | `/api/super-admin/companies` | — | — | `CompanyCreateWithAdmin` | `verify_super_admin` | 200, 400, 403, 500 |
| 5 | PATCH | `/api/super-admin/companies/{company_id}` | — | `company_id` | `CompanyUpdate` | `verify_super_admin` | 200, 400, 403, 404, 500 |
| 6 | DELETE | `/api/super-admin/companies/{company_id}` | — | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 7 | DELETE | `/api/super-admin/companies/{company_id}/permanent` | — | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 8 | GET | `/api/super-admin/users` | `skip`, `limit`, `company_id`, `role`, `search` | — | — | `verify_super_admin` | 200, 403, 500 |
| 9 | GET | `/api/super-admin/companies/{company_id}/users` | `role` | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 10 | POST | `/api/super-admin/companies/{company_id}/users` | — | `company_id` | `UserCreate` | `verify_super_admin` | 200, 400, 403, 404, 500 |
| 11 | PATCH | `/api/super-admin/companies/{company_id}/users/{user_id}` | — | `company_id`, `user_id` | `dict` (free-form) | `verify_super_admin` | 200, 400, 403, 404, 500 |
| 12 | DELETE | `/api/super-admin/companies/{company_id}/users/{user_id}` | — | `company_id`, `user_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 13 | GET | `/api/super-admin/system/health` | — | — | — | `verify_super_admin` | 200 (body `status`/`checks` ou `status: error`) |
| 14 | GET | `/api/super-admin/super-admins` | — | — | — | `verify_super_admin` | 200, 403, 500 |
| 15 | POST | `/api/super-admin/reduction-fillon/calculate` | — | — | `ReductionFillonRequest` | `verify_super_admin` | 200, 403, 404, 500 |
| 16 | GET | `/api/super-admin/reduction-fillon/employees` | — | — | — | `verify_super_admin` | 200, 403, 500 |

**Prefix legacy :** `/api/super-admin`  
**Tags legacy :** `["Super Admin"]`  
**Dépendance legacy :** `verify_super_admin(current_user: User = Depends(get_current_user))` → lit `super_admins` via Supabase, retourne la ligne (dict) ou 403.

---

## 2. Liste des routes du nouveau router

| # | Méthode | Chemin complet | Query params | Path params | Body | Dépendance | Codes HTTP (via _map_exceptions) |
|---|--------|----------------|--------------|-------------|------|------------|----------------------------------|
| 1 | GET | `/api/super-admin/dashboard/stats` | — | — | — | `verify_super_admin` | 200, 403, 500 |
| 2 | GET | `/api/super-admin/companies` | `skip`, `limit`, `search`, `is_active` | — | — | `verify_super_admin` | 200, 403, 500 |
| 3 | GET | `/api/super-admin/companies/{company_id}` | — | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 4 | POST | `/api/super-admin/companies` | — | — | `CompanyCreateWithAdmin` | `verify_super_admin` | 200, 400, 403, 500 |
| 5 | PATCH | `/api/super-admin/companies/{company_id}` | — | `company_id` | `CompanyUpdate` | `verify_super_admin` | 200, 400, 403, 404, 500 |
| 6 | DELETE | `/api/super-admin/companies/{company_id}` | — | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 7 | DELETE | `/api/super-admin/companies/{company_id}/permanent` | — | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 8 | GET | `/api/super-admin/users` | `skip`, `limit`, `company_id`, `role`, `search` | — | — | `verify_super_admin` | 200, 403, 500 |
| 9 | GET | `/api/super-admin/companies/{company_id}/users` | `role` | `company_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 10 | POST | `/api/super-admin/companies/{company_id}/users` | — | `company_id` | `UserCreate` | `verify_super_admin` | 200, 400, 403, 404, 500 |
| 11 | PATCH | `/api/super-admin/companies/{company_id}/users/{user_id}` | — | `company_id`, `user_id` | `Body(...)` (dict) | `verify_super_admin` | 200, 400, 403, 404, 500 |
| 12 | DELETE | `/api/super-admin/companies/{company_id}/users/{user_id}` | — | `company_id`, `user_id` | — | `verify_super_admin` | 200, 403, 404, 500 |
| 13 | GET | `/api/super-admin/system/health` | — | — | — | `verify_super_admin` | 200 (body identique ou `status: error`) |
| 14 | GET | `/api/super-admin/super-admins` | — | — | — | `verify_super_admin` | 200, 403, 500 |
| 15 | POST | `/api/super-admin/reduction-fillon/calculate` | — | — | `ReductionFillonRequest` | `verify_super_admin` | 200, 403, 404, 500 |
| 16 | GET | `/api/super-admin/reduction-fillon/employees` | — | — | — | `verify_super_admin` | 200, 403, 500 |

**Prefix nouveau :** `/api/super-admin`  
**Tags nouveau :** `["Super Admin"]`  
**Dépendance nouveau :** `verify_super_admin(current_user: User = Depends(get_current_user))` → appelle `application.service.verify_super_admin_and_return_row(current_user.id)`, retourne dict ou 403.

---

## 3. Correspondances exactes

Toutes les 16 routes legacy ont une route équivalente dans le nouveau router :

| Legacy (méthode + path) | Nouveau (méthode + path) | Alignement |
|-------------------------|---------------------------|------------|
| GET /dashboard/stats | GET /dashboard/stats | ✅ |
| GET /companies | GET /companies | ✅ (query: skip, limit, search, is_active) |
| GET /companies/{company_id} | GET /companies/{company_id} | ✅ |
| POST /companies | POST /companies | ✅ (body: CompanyCreateWithAdmin) |
| PATCH /companies/{company_id} | PATCH /companies/{company_id} | ✅ (body: CompanyUpdate) |
| DELETE /companies/{company_id} | DELETE /companies/{company_id} | ✅ |
| DELETE /companies/{company_id}/permanent | DELETE /companies/{company_id}/permanent | ✅ |
| GET /users | GET /users | ✅ (query: skip, limit, company_id, role, search) |
| GET /companies/{company_id}/users | GET /companies/{company_id}/users | ✅ (query: role) |
| POST /companies/{company_id}/users | POST /companies/{company_id}/users | ✅ (body: UserCreate) |
| PATCH /companies/{company_id}/users/{user_id} | PATCH /companies/{company_id}/users/{user_id} | ✅ (body: dict via Body(...)) |
| DELETE /companies/{company_id}/users/{user_id} | DELETE /companies/{company_id}/users/{user_id} | ✅ |
| GET /system/health | GET /system/health | ✅ |
| GET /super-admins | GET /super-admins | ✅ |
| POST /reduction-fillon/calculate | POST /reduction-fillon/calculate | ✅ (body: ReductionFillonRequest) |
| GET /reduction-fillon/employees | GET /reduction-fillon/employees | ✅ |

---

## 4. Routes manquantes

**Aucune.** Toutes les routes legacy sont présentes dans le nouveau router.

---

## 5. Routes en trop

**Aucune.** Le nouveau router n’expose que les 16 routes listées ci-dessus, sans route supplémentaire.

---

## 6. Différences de signature ou de comportement HTTP

| Point | Legacy | Nouveau | Impact |
|-------|--------|---------|--------|
| **Auth / User** | `from security import User, get_current_user` | `from app.core.security import get_current_user` + `User` depuis `app.modules.users.schemas.responses` | Aucun sur le contrat HTTP ; même flux (JWT → user → verify super_admin). |
| **verify_super_admin** | Lit directement `supabase.table("super_admins")` avec `current_user.id` | Appelle `application.service.verify_super_admin_and_return_row(current_user.id)` (repository + mappers) | Comportement équivalent : 403 si pas super_admin ou erreur, sinon retourne la ligne (dict). |
| **CompanyUpdate** | `company_update.dict()` (Pydantic v1) | `company_update.model_dump()` (Pydantic v2) | Même sémantique ; filtrage `if v is not None` identique. |
| **PATCH user body** | `update_data: dict` (sans Body explicite) | `update_data: Dict[str, Any] = Body(...)` | Même contrat : body JSON libre (first_name, last_name, role, email). |
| **Erreurs** | HTTPException levées manuellement dans chaque route | `_map_exceptions(e)` : SuperAdminAccessError→403, LookupError→404, ValueError→400, RuntimeError/autre→500 | Mêmes codes et messages si l’infra lève les bonnes exceptions (confirmé dans infra). |
| **GET /system/health** | En cas d’exception : `return {"status": "error", "error": str(e)}` (200) | Idem : `return {"status": "error", "error": str(e)}` | Comportement identique. |
| **Permissions create/delete company** | Vérification `super_admin.get("can_create_companies")` / `can_delete_companies` dans le routeur | Vérification dans `application.commands` via `domain.rules` (require_can_create_companies / require_can_delete_companies), puis SuperAdminAccessError → 403 dans le router | Même résultat HTTP 403 et message. |

Aucune divergence de signature ou de code HTTP identifiée pour les cas vérifiés.

---

## 7. Dépendances FastAPI importantes

| Dépendance | Legacy | Nouveau |
|------------|--------|--------|
| **Authentification** | `get_current_user` (security) | `get_current_user` (app.core.security) |
| **Guard super_admin** | `verify_super_admin` (lecture table super_admins) | `verify_super_admin` (service → repository) |
| **Tags** | `tags=["Super Admin"]` sur le router | `tags=["Super Admin"]` sur le router |
| **Prefix** | `prefix="/api/super-admin"` | `prefix="/api/super-admin"` |

Aucune dépendance FastAPI critique manquante ou modifiée au sens du comportement documentaire ou client.

---

## 8. Permissions / guards / auth

- **Legacy :** Toutes les routes dépendent de `verify_super_admin`. POST /companies et DELETE /companies (soft et permanent) vérifient en plus `can_create_companies` et `can_delete_companies` sur la ligne super_admin.
- **Nouveau :** Idem : toutes les routes utilisent `verify_super_admin`. Les vérifications `can_create_companies` et `can_delete_companies` sont faites dans `application.commands` (create_company_with_admin, delete_company_soft, delete_company_permanent) via le domaine ; en cas de refus, `SuperAdminAccessError` est levée et le router renvoie 403.

Comportement auth et permissions aligné.

---

## 9. Tags et documentation

- **Legacy :** `APIRouter(prefix="/api/super-admin", tags=["Super Admin"])`.
- **Nouveau :** `APIRouter(prefix="/api/super-admin", tags=["Super Admin"])`.

Aucune différence pour la doc OpenAPI ou le regroupement par tag.

---

## 10. Verdict final

**Migration complète conforme.**

- Les 16 routes legacy sont toutes présentes dans le nouveau router avec les mêmes méthode HTTP, préfixe, chemins, paramètres de query, paramètres de path et body.
- Les codes de statut et la sémantique des réponses (y compris GET /system/health en erreur) sont conservés.
- Les dépendances (get_current_user, verify_super_admin), les permissions (can_create_companies, can_delete_companies) et les tags sont équivalents.
- Aucune route manquante, aucune route en trop, aucune divergence de signature ou de comportement HTTP identifiée.

**Note :** L’ancien système (`api/routers/super_admin.py` monté dans `main.py`) reste en place pour compatibilité. Aucune route legacy n’a été supprimée ; le nouveau router peut être utilisé en parallèle (ex. via `app/api/router.py`) jusqu’à bascule complète. Si une route legacy est encore nécessaire côté appelants, elle reste disponible tant que l’ancien router est inclus dans l’application.
