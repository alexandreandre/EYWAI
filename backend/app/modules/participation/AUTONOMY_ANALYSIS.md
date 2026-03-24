# Analyse d'autonomie — app/modules/participation

## Étape A — Imports et dépendances

### Imports dirigés vers l’extérieur du module (hors app/modules/participation)

| Fichier | Import | Symbole(s) | Usage | Type | Cible correcte |
|---------|--------|------------|--------|------|------------------|
| api/router.py | app.core.security | get_current_user | Dépendance FastAPI auth | Sécurité transverse | app/core/* (déjà conforme) |
| api/router.py | app.modules.users.schemas.responses | User | Type du paramètre user (_require_company_id, routes) | Schéma autre module | Protocol local (contrat minimal) |
| infrastructure/queries.py | app.core.database | supabase | Client DB pour employees, employee_schedules, payslips | Accès DB | app/core/* (déjà conforme) |
| infrastructure/repository.py | app.core.database | supabase | Client DB pour participation_simulations | Accès DB | app/core/* (déjà conforme) |

### Dépendances legacy (hors app/*)

- **Aucune.** Aucun fichier du module n’importe depuis api/*, schemas/*, services/*, core legacy (backend_api/core), backend_calculs/* ou tout chemin hors app/*.

### Dépendance à supprimer pour autonomie structurelle

- **app.modules.users.schemas.responses.User** : utilisé uniquement pour le typage du contexte utilisateur (id, active_company_id). Le module peut être rendu autonome en définissant un **Protocol** local décrivant ce contrat, sans importer le type User d’un autre module (aligné sur bonus_types).

### Éléments à conserver (déjà dans app/*)

- **app.core.database.supabase** : partie de la nouvelle architecture (app/core), pas du legacy. À conserver.
- **app.core.security.get_current_user** : idem. À conserver.

### Wrappers temporaires

- Aucun wrapper de compatibilité legacy n’est nécessaire ; le module n’utilise pas d’éléments legacy hors app/*.

---

## Cible des changements (étape B)

1. **Créer** `app/modules/participation/api/dependencies.py` :
   - Définir un Protocol `ParticipationUserContext` avec `id` et `active_company_id` (contrat minimal pour les routes).
   - Réexporter `get_current_user` depuis `app.core.security` pour un point d’entrée unique si souhaité (optionnel ; le router peut continuer à importer depuis app.core.security).
2. **Modifier** `app/modules/participation/api/router.py` :
   - Remplacer l’import de `User` (app.modules.users) par l’usage du Protocol local.
   - Typer le paramètre user avec `ParticipationUserContext` et garder `Depends(get_current_user)`.
   - Conserver strictement le comportement HTTP et la logique (codes, messages, _require_company_id).

Aucun nouveau fichier dans app/shared/* : le contrat utilisateur est spécifique au besoin du router participation (id + active_company_id). Aucun déplacement de schémas ou de logique métier.

---

## Étape C — Vérification d'autonomie (après modifications)

### 1. Aucun import legacy

- Aucun fichier dans app/modules/participation n'importe : api/*, schemas/* (racine), services/*, core legacy (backend_api/core), backend_calculs/*, ni aucun chemin hors app/*.

### 2. Imports restants (tous sous app/* ou librairies)

| Fichier | Import | Sous app/* |
|---------|--------|------------|
| api/dependencies.py | app.core.security | Oui (app/core) |
| api/router.py | app.modules.participation.* | Oui (module) |
| infrastructure/queries.py | app.core.database | Oui (app/core) |
| infrastructure/repository.py | app.core.database | Oui (app/core) |
| Tous les autres | app.modules.participation.* ou stdlib/pydantic/fastapi | Oui / libs |

### 3. Comportement HTTP et métier

- Endpoints, méthodes, préfixes, paramètres, body, response models, codes de statut : inchangés.
- `get_current_user` inchangé (toujours fourni par app.core.security ; le type du paramètre est un Protocol local).
- Logique métier observable : inchangée.

---

## Verdict final

**Module autonome.** Aucun wrapper temporaire conservé. Le module ne dépend plus d’aucun autre module app (users) ; il ne dépend que de app/core (security, database) et de ses propres couches.
