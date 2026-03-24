# Analyse des dépendances legacy — module employee_exits (autonomie)

**Objectif :** Rendre le module structurellement autonome, sans importer hors `app/*` (sauf wrappers temporaires justifiés).

---

## Étape A — Imports legacy identifiés

### 1. `app/modules/employee_exits/api/router.py`

| Ligne | Import legacy | Symbole | Usage | Type |
|-------|----------------|---------|--------|------|
| 77 | `api.routers.user_management` | `check_user_has_permission` | Vérification permission `employee_documents.publish_exit_documents` dans `_check_publish_permission` | Permission / guard |
| 96 | `api.routers.user_management` | `check_user_has_permission` | Vérification permission `employee_exit.publish` dans `_check_unpublish_permission` | Permission / guard |

**Cible correcte :** `app.modules.access_control.application.service.get_access_control_service().check_user_has_permission(user_id, company_id, permission_code)` — même signature, même sémantique.

---

### 2. `app/modules/employee_exits/infrastructure/providers.py`

| Ligne | Import legacy | Symbole | Usage | Type |
|-------|----------------|---------|--------|------|
| 26 | `services.document_generator` | `EmployeeExitDocumentGenerator` | Implémentation de `IExitDocumentGenerator` (certificat de travail, attestation Pôle Emploi, solde de tout compte) | Service / provider |

**Contexte :** Le générateur legacy dépend de `services.solde_common.pdf_helpers` et `services.solde_cases.*` (plusieurs modules). Déplacer tout le code dans `app/*` nécessiterait une migration lourde de ces services.

**Cible :** Créer un wrapper de compatibilité sous `app/shared/compat/` qui importe le legacy et expose une fabrique retournant un adaptateur implémentant `IExitDocumentGenerator`. Le module n’importe plus que `app.shared.compat.*`.

---

### 3. `app/modules/employee_exits/infrastructure/providers.py` (backend_calculs)

| Ligne | Import | Symbole | Usage | Type |
|-------|--------|---------|--------|------|
| 85-86 | `backend_calculs.moteur_paie.calcul_indemnites_sortie` | `calculer_indemnites_sortie` | Calcul des indemnités de sortie (moteur métier externe) | Package externe / calcul métier |

**Décision :** Conserver temporairement comme **wrapper autorisé**. Justification : package de calcul métier partagé, non migré dans `app/*` ; la migration sort du périmètre du module employee_exits. Le module garde un import lazy dans `infrastructure/providers.py` avec justification documentée.

---

## Dépendances déjà sous app/* (conservées)

- `app.core.database` (supabase) — accès DB transverse.
- `app.core.security` (get_current_user) — auth transverse.
- `app.modules.users.schemas.responses` (User) — modèle utilisateur partagé.
- `app.modules.employee_exits.*` — internes au module.

Aucune modification nécessaire pour ces imports.

---

## Récapitulatif des cibles

| Dépendance legacy | Action | Cible |
|-------------------|--------|--------|
| `api.routers.user_management.check_user_has_permission` | Remplacer | `app.modules.access_control.application.service.get_access_control_service().check_user_has_permission` |
| `services.document_generator.EmployeeExitDocumentGenerator` | Déplacer vers wrapper sous app | `app.shared.compat.employee_exit_document_generator` (wrapper qui importe le legacy) |
| `backend_calculs.moteur_paie.calcul_indemnites_sortie` | Conserver (wrapper temporaire autorisé) | Aucun changement ; documenter dans le module |

---

## Wrappers temporaires conservés (avec justification)

1. **backend_calculs** (dans `infrastructure/providers.py`)  
   - **Justification :** Moteur de calcul des indemnités de sortie, package métier externe au repo ou non migré dans `app/*`. La réécriture ou la migration du package sort du périmètre du module. Import lazy conservé, explicitement documenté comme dépendance temporaire autorisée.

---

## Étape B — Modifications appliquées

### Imports legacy supprimés (dans le module)

| Fichier | Import supprimé |
|---------|------------------|
| `api/router.py` | `from api.routers.user_management import check_user_has_permission` (×2, dans _check_publish_permission et _check_unpublish_permission) |
| `infrastructure/providers.py` | `from services.document_generator import EmployeeExitDocumentGenerator` + classe _ExitDocumentGeneratorAdapter déplacée |

### Nouveaux fichiers créés ou complétés sous app/*

| Fichier | Rôle |
|---------|------|
| `app/shared/compat/__init__.py` | Package des wrappers de compatibilité legacy → app |
| `app/shared/compat/employee_exit_document_generator.py` | Wrapper : importe `services.document_generator`, expose `get_employee_exit_document_generator()` retournant un `IExitDocumentGenerator` (adaptateur). Seul point d’entrée app/* vers le générateur legacy. |

### Fichiers modifiés (diffs ciblés)

- **app/modules/employee_exits/api/router.py**  
  - Ajout : `from app.modules.access_control.application.service import get_access_control_service`.  
  - `_check_publish_permission` et `_check_unpublish_permission` : remplacement du bloc try/except + `check_user_has_permission` legacy par `get_access_control_service().check_user_has_permission(...)`.

- **app/modules/employee_exits/infrastructure/providers.py**  
  - Suppression de l’import `services.document_generator` et de la classe `_ExitDocumentGeneratorAdapter`.  
  - Ajout : `from app.shared.compat.employee_exit_document_generator import get_employee_exit_document_generator`.  
  - `get_exit_document_generator()` délègue à `get_employee_exit_document_generator()`.  
  - Commentaire ajouté sur `_IndemnityCalculatorAdapter` pour le wrapper temporaire backend_calculs.

---

## Étape C — Vérification d’autonomie

1. **Aucun fichier dans `app/modules/employee_exits` n’importe désormais :**
   - `api/*` — supprimé (remplacé par access_control).
   - `schemas/*` — jamais utilisé dans le module (schemas sous `app/modules/employee_exits/schemas`).
   - `services/*` — supprimé (délégation via `app/shared/compat/employee_exit_document_generator`).
   - `core/*` legacy — non concerné ; le module utilise `app.core.database` et `app.core.security` (nouvelle architecture).

2. **Import restant hors app/modules et hors libs :**
   - `app.core.database`, `app.core.security` — autorisés (app/core).
   - `app.modules.users.schemas.responses` (User) — autorisé (app/modules).
   - `app.modules.access_control.application.service` — autorisé (app/modules).
   - `app.shared.compat.employee_exit_document_generator` — autorisé (app/shared).
   - **backend_calculs** : import lazy uniquement dans `infrastructure/providers.py` (_IndemnityCalculatorAdapter) — **wrapper temporaire autorisé**, documenté.

3. **Comportement HTTP et métier :**  
   - Endpoints, méthodes, préfixes, paramètres, body, response models, codes de statut inchangés.  
   - Permissions publish/unpublish : même sémantique (access_control repose sur le même référentiel de permissions que user_management).  
   - Génération de documents et calcul d’indemnités : même implémentation (même code appelé via wrapper ou adaptateur).

---

## Verdict final

**Module autonome avec wrappers temporaires autorisés.**

- Le module `app/modules/employee_exits` ne dépend plus d’aucun élément legacy hors `app/*`, à l’exception de **backend_calculs** (import lazy dans `infrastructure/providers.py`), conservé comme wrapper temporaire autorisé et documenté.
- Wrappers temporaires conservés : **backend_calculs** (calcul d’indemnités de sortie) ; le point d’entrée **services.document_generator** est désormais uniquement dans `app/shared/compat`, donc hors du module employee_exits.
