# Autonomie du module bonus_types

## Étape A — Analyse des dépendances (état final)

### Imports externes au module (hors app.modules.bonus_types)

| Fichier | Import | Cible | Type | Legacy ? |
|---------|--------|--------|------|----------|
| api/dependencies.py | get_current_user | app.core.security | Sécurité / auth | Non (app/core) |
| infrastructure/repository.py | supabase | app.core.database | Accès DB | Non (app/core) |
| infrastructure/providers.py | supabase | app.core.database | Accès DB | Non (app/core) |

### Imports legacy supprimés

- **app.modules.users.schemas.responses.User** (api/router.py) : remplacé par le Protocol `BonusTypeUserContext` défini dans api/dependencies.py. Le contrat (active_company_id, id, is_super_admin, has_rh_access_in_company) est décrit localement ; `get_current_user` retourne à l’exécution un objet qui satisfait ce protocole (duck typing).

### Aucun import vers

- api/*
- schemas/* (hors app)
- services/*
- core/* (racine backend_api)
- backend_calculs/*

---

## Étape B — Modifications effectuées

1. **Création de app/modules/bonus_types/api/dependencies.py**
   - Protocol `BonusTypeUserContext` : contrat minimal (active_company_id, id, is_super_admin, has_rh_access_in_company).
   - Réexport de `get_current_user` depuis `app.core.security` pour centraliser les dépendances HTTP du module.

2. **Modification de app/modules/bonus_types/api/router.py**
   - Remplacement de l’import `User` (app.modules.users) par `BonusTypeUserContext` et `get_current_user` depuis `api.dependencies`.
   - Toutes les routes typent le contexte avec `BonusTypeUserContext` au lieu de `User`.
   - Utilisation directe de `user.is_super_admin` (plus de `getattr`).

---

## Étape C — Vérification d’autonomie

1. **Aucun fichier dans app/modules/bonus_types n’importe** : api/*, schemas/*, services/*, core/* (legacy), backend_calculs/*, ni aucun chemin legacy hors app/*.
2. **Imports restants** : app.core.* (security, database), app.modules.bonus_types.* (interne), bibliothèques (fastapi, typing, etc.).
3. **Comportement** : pas de changement des endpoints, méthodes HTTP, paramètres, body, response, codes de statut ; la logique métier et le contrat HTTP restent identiques.

---

## Verdict

**Module autonome.**  
Le module ne dépend que de app.core (sécurité, base) et de ses propres couches ; plus aucune dépendance à app.modules.users ni à un chemin legacy hors app/*.
