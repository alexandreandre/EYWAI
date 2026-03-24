# Analyse du module employee_exits — Migration Phase 4

Document d’analyse pour la migration du module **employee_exits** (sorties de salariés) vers l’architecture cible. Aucune modification de code ; analyse uniquement.

---

## 1. Fichiers existants concernés

### 1.1 Fichiers legacy (à migrer ou à faire pointer vers le module)

| Fichier | Rôle | Taille / remarque |
|--------|------|-------------------|
| `api/routers/employee_exits.py` | Router FastAPI unique, toute la logique HTTP + DB + métier | ~1640 lignes |
| `schemas/employee_exit.py` | Tous les schémas Pydantic (création, mise à jour, réponses, documents, checklist, indemnités, publication) | ~405 lignes |

### 1.2 Services externes au module (dépendances)

| Fichier | Usage |
|--------|--------|
| `services/document_generator.py` | Classe `EmployeeExitDocumentGenerator` : `generate_certificat_travail`, `generate_attestation_pole_emploi`, `generate_solde_tout_compte` (dispatch vers `solde_cases`). Utilisée dans create, generate document, edit document. |
| `services/solde_common/pdf_helpers.py` | `setup_custom_styles`, `format_date`, `format_currency`, `safe_float`, `safe_str` |
| `services/solde_common/socle_commun.py` | `get_salary_prorata` (via `_get_salary_prorata` dans le generator) |
| `services/solde_cases/*` | `generate_*_solde` selon `exit_type` (demission, rupture_conventionnelle, licenciement, retraite, fin_periode_essai, generic) |
| `core.config` | `supabase` — utilisé partout dans le router (tables, storage) |
| `security` | `get_current_user`, `User` |
| `api/routers/user_management` | `check_user_has_permission` — import **conditionnel** dans `publish_exit_documents` et `unpublish_exit_document` |

### 1.3 Code hors backend_api (à ne pas déplacer)

| Emplacement | Usage |
|-------------|--------|
| `backend_calculs/moteur_paie/calcul_indemnites_sortie.py` | `calculer_indemnites_sortie(employee_data, exit_data, supabase_client)` — appelé après création de sortie et dans la route `calculate-indemnities`. |
| `main.py` | `from api.routers import employee_exits` puis `app.include_router(employee_exits.router)` |

### 1.4 Autres références à employee_exits (lecture seule ou side-effect)

| Fichier | Usage |
|--------|--------|
| `services/exports/paiement_salaires.py` | Lecture `supabase.table('employee_exits').select('employee_id, exit_type, last_working_day, status')` pour détecter les sorties et anomalies de paiement. |
| `api/routers/employees.py` | Utilise `employee_documents` (documents publiés depuis les sorties) — pas d’import direct de employee_exits. |
| Migrations | `22_create_employee_exits_system.sql`, `28_allow_rh_delete_exits.sql`, `29_add_new_exit_types.sql`, `30_create_employee_documents_table.sql`, `30_add_publish_exit_documents.sql`, `31_add_document_editing_fields.sql`, `31_add_publish_exit_documents_permission.sql` |

### 1.5 Squelette cible déjà créé (vide)

- `app/modules/employee_exits/` — structure complète (api, application, domain, infrastructure, schemas) avec placeholders.

---

## 2. Schémas associés

Tous définis dans **`schemas/employee_exit.py`** :

### Types littéraux (réutilisables en domain/enums ou schemas)

- `ExitType` : `"demission" | "rupture_conventionnelle" | "licenciement" | "depart_retraite" | "fin_periode_essai"`
- `ExitStatus` : tous les statuts (demission_*, rupture_*, licenciement_*, archivee, annulee)
- `DocumentType` : types de documents (uploadés + générés)
- `NoticeIndemnityType` : `"paid" | "waived" | "not_applicable"`
- `ChecklistCategory` : `"administratif" | "materiel" | "acces" | "legal" | "autre"`
- `NotificationType` : types de notifications

### Requêtes (requests)

- `EmployeeExitCreate`
- `EmployeeExitUpdate`
- `ExitDocumentCreate`
- `ChecklistItemCreate`
- `ChecklistItemUpdate`
- `DocumentUploadUrlRequest`
- `ExitDocumentEditRequest`
- `StatusUpdateRequest`
- `PublishExitDocumentsRequest`

### Réponses (responses)

- `EmployeeExit`
- `SimpleEmployee`
- `EmployeeExitWithDetails`
- `ExitDocument`
- `DocumentUploadUrlResponse`
- `ExitDocumentEditResponse`
- `ExitDocumentDetails`
- `ChecklistItem`
- `IndemnityDetail` / `ExitIndemnityCalculation`
- `ExitNotificationCreate` / `ExitNotification`
- `StatusTransitionResponse`
- `ExitStatistics`
- `PublishedDocumentStatus` / `PublishExitDocumentsResponse`

À répartir dans `app/modules/employee_exits/schemas/requests.py` et `responses.py` (ou garder un wrapper qui réexporte depuis l’ancien `schemas.employee_exit` pendant la transition).

---

## 3. Services utilisés

| Service | Où | Comment |
|--------|-----|--------|
| **Supabase (client)** | Partout dans le router | `from core.config import supabase` — tables : `employee_exits`, `exit_documents`, `exit_checklist_items`, `employees`, `companies` ; bucket `exit_documents` (upload, signed URLs, remove). |
| **EmployeeExitDocumentGenerator** | create_employee_exit, generate_exit_document, edit_exit_document | `from services.document_generator import EmployeeExitDocumentGenerator` — 3 méthodes : certificat de travail, attestation Pôle Emploi, solde de tout compte. |
| **calculer_indemnites_sortie** | create_employee_exit, calculate_exit_indemnities | `from backend_calculs.moteur_paie.calcul_indemnites_sortie import calculer_indemnites_sortie` — appel avec `employee_data`, `exit_data`, `supabase_client`. |
| **get_current_user** | Toutes les routes | `from security import get_current_user, User` — dépendance FastAPI. |
| **check_user_has_exit_permission** | create, list, delete, (unpublish) | Défini dans le router : super_admin ou role admin/rh dans la company ; pas encore de permission granulaire (TODO). |
| **check_user_has_permission** | publish_exit_documents, unpublish_exit_document | Import conditionnel depuis `api.routers.user_management` — permissions `employee_documents.publish_exit_documents` et `employee_exit.publish`. |

---

## 4. Dépendances vers d’autres modules / briques

### 4.1 Base de données (tables)

- **employee_exits** — table principale (migration 22, 29 pour exit_type).
- **exit_documents** — documents liés (migration 22, 30 pour published_*, 31 pour document_data, version, manually_edited, last_edited_*).
- **exit_checklist_items** — checklist par sortie.
- **exit_notifications** — définie en migration (peu ou pas utilisée dans le router actuel).
- **employees** — lecture (company_id, employment_status, current_exit_id, infos pour génération) ; mise à jour (employment_status, current_exit_id) à la création, suppression, passage au statut « archivee ».
- **companies** — lecture pour génération de documents.
- **profiles** — initiated_by, validated_by, archived_by, uploaded_by, etc.
- **employee_documents** — création/mise à jour lors de la publication de documents de sortie.
- **exit_document_publications** — audit des publications.

### 4.2 Permissions

- **employee_exit.*** (migration 22) : view_own, view_all, create, update, validate, approve, delete, export, archive, download.
- **employee_exit.publish** (migration 30) — utilisé pour unpublish.
- **employee_documents.publish_exit_documents** (migration 31) — utilisé pour publish.

Logique actuelle :  
- create / list / delete : `check_user_has_exit_permission` (admin/rh ou super_admin).  
- publish : super_admin OU `has_rh_access_in_company` OU `check_user_has_permission(..., 'employee_documents.publish_exit_documents')`.  
- unpublish : `check_user_has_exit_permission(..., 'publish')` puis fallback `check_user_has_permission(..., 'employee_exit.publish')`.

### 4.3 Auth / contexte

- **security** : `get_current_user`, modèle `User` (avec `is_super_admin`, `active_company_id`, `get_role_in_company`, `has_rh_access_in_company`).
- **user_management** : `check_user_has_permission` (import conditionnel, à garder ou remplacer par access_control plus tard).

### 4.4 Règles métier transverses

- **Absences** : trigger SQL `check_employee_exit_status_before_absence` empêche de créer des absences pour un salarié en sortie (référence à `employee_exits`).
- **Exports** : `paiement_salaires.py` lit `employee_exits` pour les anomalies.

---

## 5. Répartition cible api / application / domain / infrastructure / schemas

### 5.1 api/

- **router.py** :  
  - Garder le **préfixe** `prefix="/api/employee-exits"` et les **tags** identiques.  
  - Déclaration des routes uniquement : validation des entrées (schemas), appel de l’application (commands/queries), renvoi des réponses.  
  - Pas d’accès direct à `supabase` ni de logique métier (transitions de statut, calculs, génération PDF, publication).  
  - Dépendances injectées : `get_current_user`, et si besoin un « permission checker » qui encapsule `check_user_has_exit_permission` + `check_user_has_permission` pour publish/unpublish.

### 5.2 application/

- **commands.py** :  
  - Create exit, update exit, update status, delete exit.  
  - Create document (upload), generate document, delete document, edit document.  
  - Publish / unpublish documents.  
  - Checklist : add item, mark complete, delete item.  
  - Chaque command orchestre : domain (règles, entités), repository, document generator, calcul indemnités, storage.  
- **queries.py** :  
  - List exits (avec filtres), get exit by id, get checklist, list documents, get document details, get document edit history, calculate indemnities (lecture + appel moteur).  
- **service.py** :  
  - Logique partagée si besoin (ex. « enrichir une sortie avec documents + checklist + taux complétion »).  
- **dto.py** :  
  - DTOs internes (sortie enrichie, document avec URL, etc.) si différents des schémas API.

### 5.3 domain/

- **entities.py** :  
  - Entité principale type `EmployeeExit` (type, statut, dates, préavis, indemnités, etc.) ; éventuellement `ExitDocument`, `ChecklistItem` si on les modélise en domain.  
- **value_objects.py** :  
  - ExitType, ExitStatus, NoticeIndemnityType, ChecklistCategory, etc. (ou réutiliser les Literal depuis les schemas).  
- **rules.py** :  
  - `get_initial_status(exit_type)`, `get_valid_status_transitions(exit_type, current_status)` ; règle période de rétractation 15 jours (rupture conventionnelle) ; règles « employé sans sortie active », « pas d’absence si en sortie » (côté absences).  
- **enums.py** :  
  - Énumérations pour exit_type, status, document_type, etc. (alignées sur les schémas).  
- **interfaces.py** :  
  - Ports : `IEmployeeExitRepository`, `IExitDocumentRepository`, `IChecklistRepository`, `IExitDocumentGenerator`, `IIndemnityCalculator`, `IStorage`, etc.

### 5.4 infrastructure/

- **repository.py** :  
  - Implémentation des repositories (employee_exits, exit_documents, exit_checklist_items) — CRUD Supabase, sans logique métier.  
- **queries.py** :  
  - Requêtes métier complexes : list exits with employee, get exit with documents + signed URLs, checklist with completion rate, etc.  
- **mappers.py** :  
  - Row DB / dict Supabase ↔ entités domain (ou DTOs).  
- **providers.py** :  
  - Adapter vers `EmployeeExitDocumentGenerator` (existant dans `services/`) et vers `calculer_indemnites_sortie` (backend_calculs) ; adapter Storage (signed URL, upload, remove) pour le bucket `exit_documents`.  

Option : garder `EmployeeExitDocumentGenerator` dans `services/` et l’injecter depuis l’application via une interface du module (ex. `IExitDocumentGenerator`) pour ne pas casser les imports existants (document_generator utilisé ailleurs potentiellement).

### 5.5 schemas/

- **requests.py** :  
  - EmployeeExitCreate, EmployeeExitUpdate, ExitDocumentCreate, ChecklistItemCreate/Update, DocumentUploadUrlRequest, ExitDocumentEditRequest, StatusUpdateRequest, PublishExitDocumentsRequest.  
- **responses.py** :  
  - EmployeeExit, EmployeeExitWithDetails, ExitDocument, ExitDocumentDetails, ExitDocumentEditResponse, ChecklistItem, ExitIndemnityCalculation, StatusTransitionResponse, DocumentUploadUrlResponse, PublishedDocumentStatus, PublishExitDocumentsResponse, etc.  
- **__init__.py** :  
  - Réexport pour garder un point d’entrée unique (et compatibilité avec un ancien `from schemas.employee_exit import ...` si wrapper conservé côté legacy).

---

## 6. Points à garder strictement identiques

### 6.1 Contrat API (frontend et autres clients)

- **Préfixe des routes** : `/api/employee-exits` (aucun changement d’URL).
- **Méthodes et chemins** :  
  - `POST /`, `GET /`, `GET /{exit_id}`, `PATCH /{exit_id}`, `PATCH /{exit_id}/status`, `DELETE /{exit_id}`  
  - `POST /{exit_id}/calculate-indemnities`  
  - `POST /{exit_id}/documents/upload-url`, `POST /{exit_id}/documents`, `GET /{exit_id}/documents`, `POST /{exit_id}/documents/generate/{document_type}`, `DELETE /{exit_id}/documents/{document_id}`  
  - `POST /{exit_id}/documents/publish`, `POST /{exit_id}/documents/{document_id}/unpublish`  
  - `GET /{exit_id}/documents/{document_id}/details`, `POST /{exit_id}/documents/{document_id}/edit`, `GET /{exit_id}/documents/{document_id}/history`  
  - `GET /{exit_id}/checklist`, `POST /{exit_id}/checklist`, `PATCH /{exit_id}/checklist/{item_id}/complete`, `DELETE /{exit_id}/checklist/{item_id}`  
- **Schémas de requête/réponse** : noms de champs et types inchangés (y compris Literal, Optional, structures imbriquées) pour ne pas casser le frontend (`frontend/src/api/employeeExits.ts`, pages Exit, ExitDocumentEdit, etc.).

### 6.2 Permissions

- Comportement actuel à préserver :  
  - **create / list / delete** : `check_user_has_exit_permission` (super_admin ou admin/rh dans la company).  
  - **publish** : super_admin OU `has_rh_access_in_company(company_id)` OU `check_user_has_permission(user_id, company_id, 'employee_documents.publish_exit_documents')`.  
  - **unpublish** : `check_user_has_exit_permission(..., 'publish')` puis fallback `check_user_has_permission(..., 'employee_exit.publish')`.  
- Ne pas supprimer les permissions existantes (employee_exit.*, employee_exit.publish, employee_documents.publish_exit_documents) ni changer les codes de permission.

### 6.3 Documents

- **Génération** : les 3 types (certificat de travail, attestation Pôle Emploi, solde de tout compte) doivent rester générés par `EmployeeExitDocumentGenerator` avec la même signature et le même comportement (y compris dispatch par `exit_type` pour le solde).  
- **Stockage** : bucket `exit_documents`, chemins `exits/{exit_id}/...`, même structure d’enregistrement en base (`exit_documents` avec document_type, document_category, storage_path, generation_data, version, manually_edited, etc.).  
- **Publication** : même logique (idempotence via source_exit_document_id, force_update, écriture dans `employee_documents` et `exit_document_publications`).  
- **Édition** : même flux (document_data, version, manually_edited, last_edited_by, last_edited_at, régénération PDF, update storage).

### 6.4 Indemnités

- Utilisation de `calculer_indemnites_sortie(employee_data, exit_data, supabase_client)` (backend_calculs) sans changer la signature ni le comportement.  
- Mise à jour des champs `calculated_indemnities`, `remaining_vacation_days`, `final_net_amount` sur `employee_exits` identique.

### 6.5 Données et règles métier

- **Statut employé** : à la création de sortie → `employment_status = 'en_sortie'`, `current_exit_id` ; à archivage → `employment_status = 'parti'`, `current_exit_id = None` ; à suppression sortie → `employment_status = 'actif'`, `current_exit_id = None`.  
- **Checklist par défaut** : même liste d’items (badge_return, equipment_return, email_deactivation, etc.) créée à la création de sortie.  
- **Transitions de statut** : même carte `get_valid_status_transitions` ; même règle des 15 jours pour rupture conventionnelle (rupture_validee → rupture_effective).  
- **Suppression** : suppression des fichiers dans le bucket `exit_documents` pour la sortie, puis CASCADE en base (exit_documents, exit_checklist_items, etc.), puis remise de l’employé en actif.

### 6.6 Imports et compatibilité

- **Imports lazy** : le router actuel utilise un import conditionnel `from api.routers.user_management import check_user_has_permission` uniquement dans publish/unpublish. En migration, garder un comportement équivalent (éviter d’importer user_management au chargement du module si possible, ou documenter la dépendance).  
- **Wrappers** : si l’ancien `api/routers/employee_exits.py` est remplacé par un include du router du module, les anciens chemins `schemas.employee_exit` et `services.document_generator` peuvent rester utilisés par d’autres parties du projet ; le module peut soit dupliquer les schemas et les garder alignés, soit exposer des wrappers qui réexportent depuis l’ancien emplacement jusqu’à migration complète.

### 6.7 Base de données

- Aucune migration SQL à ajouter pour cette phase : ne pas renommer tables ni colonnes, ne pas changer les contraintes, RLS ou triggers existants (notamment `check_employee_exit_status_before_absence`).

---

## 7. Risques et précautions

- **Permissions** : double logique (check_user_has_exit_permission + check_user_has_permission) à reproduire à l’identique pour publish/unpublish.  
- **Documents** : forte dépendance à `EmployeeExitDocumentGenerator` et à `solde_cases`/`solde_common` ; garder le même point d’entrée (services/document_generator) ou bien définir une interface dans le module et un adapter dans infrastructure.  
- **backend_calculs** : import depuis un package externe au backend API ; ne pas déplacer ce code, seulement l’appeler depuis l’application (ou un provider) du module.  
- **Frontend** : aucune modification des URLs ni des payloads pour éviter de casser `employeeExits.ts` et les pages associées.

---

*Document généré pour la Phase 4 — migration du module employee_exits. Ne pas modifier les fichiers listés ; utiliser ce document comme référence pour la migration.*
