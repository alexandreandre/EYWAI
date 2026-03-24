# Analyse d'autonomie — module collective_agreements

## Étape A — Dépendances externes au module

### Imports dirigés vers l’extérieur du module (hors stdlib / libs externes)

| Fichier | Import | Symbole(s) | Usage | Cible dans la nouvelle architecture |
|---------|--------|------------|--------|-------------------------------------|
| `api/dependencies.py` | `from app.core.security import` | `get_current_user` | Dépendance FastAPI pour l’auth sur les routes | `app.core.security` (transverse) — **autorisé** |
| `infrastructure/repository.py` | `from app.core.database import` | `get_supabase_client` | Client Supabase pour les tables catalogue / assignations | `app.core.database` (transverse) — **autorisé** |
| `infrastructure/providers.py` | `from app.core.database import` | `get_supabase_client` | Client Supabase pour storage + table cache texte | `app.core.database` (transverse) — **autorisé** |

### Imports internes au module (app.modules.collective_agreements.*)

Tous les autres imports du module pointent vers :
- `app.modules.collective_agreements.application.*`
- `app.modules.collective_agreements.domain.*`
- `app.modules.collective_agreements.infrastructure.*`
- `app.modules.collective_agreements.schemas.*`
- `app.modules.collective_agreements.api.dependencies`

Aucun import vers : `api/*`, `schemas/*`, `services/*`, `core/*` (legacy), `backend_calculs/*`, ni aucun chemin hors `app/*`.

### Dépendances transitives (app.core)

- `app.core.database` → `app.core.settings` (env Supabase) ; pas de legacy.
- `app.core.security` → `app.core.database`, `app.modules.users.schemas.responses` (User, CompanyAccess) ; tout sous `app/*`.

## Wrappers de compatibilité conservés

- **Aucun dans le module.** Le module n’utilise aucun wrapper legacy.
- Le fichier `backend_api/schemas/collective_agreement.py` est un **wrapper de compatibilité côté legacy** : il réexporte les schémas depuis `app.modules.collective_agreements.schemas`. Il est utilisé par les anciens routers (`api/routers/collective_agreements*.py`), pas par le module. Aucune action requise dans le module.

## Étape B — Modifications appliquées

Aucune modification de code nécessaire pour l’autonomie. Le module ne dépend déjà que de :
- `app.core.*` (database, security)
- `app.modules.collective_agreements.*` (interne)
- stdlib et librairies externes (fastapi, pydantic, pdfplumber, requests, openai).

## Étape C — Vérification

1. Aucun fichier dans `app/modules/collective_agreements` n’importe depuis : `api/*`, `schemas/*`, `services/*`, `core/*` (legacy), ni aucun chemin legacy hors `app/*`.
2. Les seuls imports « externes au module » pointent vers : `app.core.database`, `app.core.security`.
3. Comportement HTTP et métier inchangé (aucune modification effectuée).

## Verdict

**Module autonome.** Il ne dépend que de `app/core/*`, de ses propres sous-packages et des bibliothèques externes. Aucun wrapper temporaire requis dans le module.
