# Vérification exhaustive des routes employee_exits — Legacy vs nouveau router

**Date :** 2025-03-13  
**Règle :** Aucun fichier modifié ou supprimé. Comparaison stricte des deux routeurs.

---

## 1. Préfixe et tags

| Élément | Legacy (`api/routers/employee_exits.py`) | Nouveau (`app/modules/employee_exits/api/router.py`) | Conforme |
|--------|----------------------------------------|------------------------------------------------------|----------|
| **prefix** | `/api/employee-exits` | `/api/employee-exits` | Oui |
| **tags** | `["Employee Exits"]` | `["Employee Exits"]` | Oui |

---

## 2. Liste des routes legacy (ordre de déclaration)

| # | Méthode | Path (relatif au préfixe) | Path params | Query params | Body | response_model | status_code | Permission / guard |
|---|--------|---------------------------|-------------|--------------|------|----------------|-------------|--------------------|
| 1 | POST | `/` | — | — | EmployeeExitCreate | EmployeeExit | 201 | company_id via employé ; `check_user_has_exit_permission(..., 'create')` |
| 2 | GET | `/` | — | status, exit_type, employee_id (Optional[str]) | — | List[EmployeeExitWithDetails] | 200 (défaut) | company_id requis (400 si absent) ; `check_user_has_exit_permission(..., 'view_all')` |
| 3 | GET | `/{exit_id}` | exit_id: UUID | — | — | EmployeeExitWithDetails | 200 | company_id = active_company_id (pas de 400 si absent) |
| 4 | PATCH | `/{exit_id}` | exit_id: UUID | — | EmployeeExitUpdate | EmployeeExit | 200 | — |
| 5 | PATCH | `/{exit_id}/status` | exit_id: UUID | — | StatusUpdateRequest | StatusTransitionResponse | 200 | — |
| 6 | DELETE | `/{exit_id}` | exit_id: UUID | — | — | — | 204 | company_id requis (400) ; `check_user_has_exit_permission(..., 'delete')` |
| 7 | POST | `/{exit_id}/calculate-indemnities` | exit_id: UUID | — | — | ExitIndemnityCalculation | 200 | company_id = active_company_id |
| 8 | POST | `/{exit_id}/documents/upload-url` | exit_id: UUID | — | DocumentUploadUrlRequest | DocumentUploadUrlResponse | 200 | company_id = active_company_id |
| 9 | POST | `/{exit_id}/documents` | exit_id: UUID | — | ExitDocumentCreate | ExitDocument | 201 | company_id = active_company_id |
| 10 | GET | `/{exit_id}/documents` | exit_id: UUID | — | — | List[ExitDocument] | 200 | company_id = active_company_id |
| 11 | POST | `/{exit_id}/documents/generate/{document_type}` | exit_id, document_type | — | — | *(aucun)* → dict | 200 | company_id = active_company_id |
| 12 | DELETE | `/{exit_id}/documents/{document_id}` | exit_id, document_id: UUID | — | — | — | 204 | company_id = active_company_id |
| 13 | POST | `/{exit_id}/documents/publish` | exit_id: UUID | — | PublishExitDocumentsRequest | PublishExitDocumentsResponse | 200 | company_id requis (400) ; super_admin OU has_rh OU check_user_has_permission(..., 'employee_documents.publish_exit_documents') |
| 14 | POST | `/{exit_id}/documents/{document_id}/unpublish` | exit_id, document_id: UUID | — | — | ExitDocument | 200 | company_id requis (400) ; check_user_has_exit_permission(..., 'publish') OU check_user_has_permission(..., 'employee_exit.publish') |
| 15 | GET | `/{exit_id}/documents/{document_id}/details` | exit_id, document_id: UUID | — | — | ExitDocumentDetails | 200 | company_id = active_company_id |
| 16 | POST | `/{exit_id}/documents/{document_id}/edit` | exit_id, document_id: UUID | — | ExitDocumentEditRequest | ExitDocumentEditResponse | 200 | company_id = active_company_id |
| 17 | GET | `/{exit_id}/documents/{document_id}/history` | exit_id, document_id: UUID | — | — | *(aucun)* → dict | 200 | company_id = active_company_id |
| 18 | GET | `/{exit_id}/checklist` | exit_id: UUID | — | — | List[ChecklistItem] | 200 | company_id = active_company_id |
| 19 | POST | `/{exit_id}/checklist` | exit_id: UUID | — | ChecklistItemCreate | ChecklistItem | 201 | company_id = active_company_id |
| 20 | PATCH | `/{exit_id}/checklist/{item_id}/complete` | exit_id, item_id: UUID | — | ChecklistItemUpdate | *(implicite ChecklistItem)* | 200 | company_id = active_company_id |
| 21 | DELETE | `/{exit_id}/checklist/{item_id}` | exit_id, item_id: UUID | — | — | — | 204 | company_id = active_company_id |

---

## 3. Liste des routes du nouveau router (ordre de déclaration)

| # | Méthode | Path (relatif au préfixe) | Path params | Query params | Body | response_model | status_code | Permission / guard |
|---|--------|---------------------------|-------------|--------------|------|----------------|-------------|--------------------|
| 1 | POST | `/` | — | — | EmployeeExitCreate | EmployeeExit | 201 | company_id via get_employee_company_id ; _check_exit_permission(..., 'create') |
| 2 | GET | `/` | — | status, exit_type, employee_id (Optional[str]) | — | List[EmployeeExitWithDetails] | 200 | _company_id_required ; _check_exit_permission(..., 'view_all') |
| 3 | GET | `/{exit_id}` | exit_id: UUID | — | — | EmployeeExitWithDetails | 200 | _company_id_required |
| 4 | PATCH | `/{exit_id}` | exit_id: UUID | — | EmployeeExitUpdate | EmployeeExit | 200 | _company_id_required |
| 5 | PATCH | `/{exit_id}/status` | exit_id: UUID | — | StatusUpdateRequest | StatusTransitionResponse | 200 | _company_id_required |
| 6 | DELETE | `/{exit_id}` | exit_id: UUID | — | — | — | 204 | _company_id_required ; _check_exit_permission(..., 'delete') |
| 7 | POST | `/{exit_id}/calculate-indemnities` | exit_id: UUID | — | — | ExitIndemnityCalculation | 200 | _company_id_required |
| 8 | POST | `/{exit_id}/documents/upload-url` | exit_id: UUID | — | DocumentUploadUrlRequest | DocumentUploadUrlResponse | 200 | _company_id_required |
| 9 | POST | `/{exit_id}/documents` | exit_id: UUID | — | ExitDocumentCreate | ExitDocument | 201 | _company_id_required |
| 10 | GET | `/{exit_id}/documents` | exit_id: UUID | — | — | List[ExitDocument] | 200 | _company_id_required |
| 11 | POST | `/{exit_id}/documents/generate/{document_type}` | exit_id, document_type | — | — | *(aucun)* → dict | 200 | _company_id_required |
| 12 | DELETE | `/{exit_id}/documents/{document_id}` | exit_id, document_id: UUID | — | — | — | 204 | _company_id_required |
| 13 | POST | `/{exit_id}/documents/publish` | exit_id: UUID | — | PublishExitDocumentsRequest | PublishExitDocumentsResponse | 200 | _company_id_required ; _check_publish_permission |
| 14 | POST | `/{exit_id}/documents/{document_id}/unpublish` | exit_id, document_id: UUID | — | — | ExitDocument | 200 | _company_id_required ; _check_unpublish_permission |
| 15 | GET | `/{exit_id}/documents/{document_id}/details` | exit_id, document_id: UUID | — | — | ExitDocumentDetails | 200 | _company_id_required |
| 16 | POST | `/{exit_id}/documents/{document_id}/edit` | exit_id, document_id: UUID | — | ExitDocumentEditRequest | ExitDocumentEditResponse | 200 | _company_id_required |
| 17 | GET | `/{exit_id}/documents/{document_id}/history` | exit_id, document_id: UUID | — | — | *(aucun)* → dict | 200 | _company_id_required |
| 18 | GET | `/{exit_id}/checklist` | exit_id: UUID | — | — | List[ChecklistItem] | 200 | _company_id_required |
| 19 | POST | `/{exit_id}/checklist` | exit_id: UUID | — | ChecklistItemCreate | ChecklistItem | 201 | _company_id_required |
| 20 | PATCH | `/{exit_id}/checklist/{item_id}/complete` | exit_id, item_id: UUID | — | ChecklistItemUpdate | *(aucun)* → ChecklistItem | 200 | _company_id_required |
| 21 | DELETE | `/{exit_id}/checklist/{item_id}` | exit_id, item_id: UUID | — | — | — | 204 | _company_id_required |

---

## 4. Correspondances exactes (Legacy → Nouveau)

Chaque route legacy a une et une seule route nouvelle de même méthode et même path :

| Legacy # | Nouveau # | Méthode | Path | Conforme |
|----------|-----------|--------|------|----------|
| 1 | 1 | POST | `/` | Oui |
| 2 | 2 | GET | `/` | Oui |
| 3 | 3 | GET | `/{exit_id}` | Oui |
| 4 | 4 | PATCH | `/{exit_id}` | Oui |
| 5 | 5 | PATCH | `/{exit_id}/status` | Oui |
| 6 | 6 | DELETE | `/{exit_id}` | Oui |
| 7 | 7 | POST | `/{exit_id}/calculate-indemnities` | Oui |
| 8 | 8 | POST | `/{exit_id}/documents/upload-url` | Oui |
| 9 | 9 | POST | `/{exit_id}/documents` | Oui |
| 10 | 10 | GET | `/{exit_id}/documents` | Oui |
| 11 | 11 | POST | `/{exit_id}/documents/generate/{document_type}` | Oui |
| 12 | 12 | DELETE | `/{exit_id}/documents/{document_id}` | Oui |
| 13 | 13 | POST | `/{exit_id}/documents/publish` | Oui |
| 14 | 14 | POST | `/{exit_id}/documents/{document_id}/unpublish` | Oui |
| 15 | 15 | GET | `/{exit_id}/documents/{document_id}/details` | Oui |
| 16 | 16 | POST | `/{exit_id}/documents/{document_id}/edit` | Oui |
| 17 | 17 | GET | `/{exit_id}/documents/{document_id}/history` | Oui |
| 18 | 18 | GET | `/{exit_id}/checklist` | Oui |
| 19 | 19 | POST | `/{exit_id}/checklist` | Oui |
| 20 | 20 | PATCH | `/{exit_id}/checklist/{item_id}/complete` | Oui |
| 21 | 21 | DELETE | `/{exit_id}/checklist/{item_id}` | Oui |

**Toutes les 21 routes legacy ont une correspondance 1:1 dans le nouveau router.**

---

## 5. Routes manquantes (dans le nouveau par rapport au legacy)

**Aucune.** Toutes les routes legacy sont présentes dans le nouveau router.

---

## 6. Routes en trop (dans le nouveau par rapport au legacy)

**Aucune.** Le nouveau router n’expose que des routes qui ont un équivalent legacy.

---

## 7. Différences de signature ou de comportement HTTP

### 7.1 Company_id requis (400 « Aucune entreprise active »)

- **Legacy :** La vérification `if not company_id: raise HTTPException(400, "Aucune entreprise active")` est faite uniquement dans : **list_employee_exits**, **delete_employee_exit**, **publish_exit_documents**, **unpublish_exit_document**. Les autres routes utilisent `company_id = current_user.active_company_id` sans lever 400 si absent (comportement potentiellement incohérent ou 404/500 en aval).
- **Nouveau :** Toutes les routes appellent `_company_id_required(current_user)`, donc **toutes** lèvent **400** si `active_company_id` est absent.

**Impact :** Le nouveau router est **plus strict et cohérent**. Pour les routes où le legacy ne vérifiait pas, un client sans entreprise active recevra désormais **400** au lieu d’éventuellement **404** ou **500**. Comportement considéré comme **amélioration**, pas divergence bloquante.

### 7.2 Message de détail 403 (permissions)

- **Legacy :** Messages variés selon la route (ex. « Vous n'avez pas les permissions pour créer une sortie de salarié », « … pour voir les sorties de salariés », « … pour supprimer une sortie », « … pour publier des documents de sortie », « … pour dépublier des documents »).
- **Nouveau :** Messages unifiés par helper : « Vous n'avez pas les permissions pour cette action sur les sorties de salariés » (_check_exit_permission), « … pour publier des documents de sortie » (_check_publish_permission), « … pour dépublier des documents » (_check_unpublish_permission).

**Impact :** Comportement HTTP identique (403), seule la chaîne de détail change. **Pas de divergence de contrat** pour un client qui ne fait que tester le code de statut.

### 7.3 Response_model déclaré

- **Legacy :**  
  - `generate_exit_document` : pas de `response_model` ; retour = dict.  
  - `get_document_edit_history` : pas de `response_model` ; retour = dict.  
  - `mark_checklist_item_complete` : pas de `response_model` ; retour = `ChecklistItem(**...)`.
- **Nouveau :** Idem (pas de `response_model` sur ces trois routes ; retour dict ou ChecklistItem).

**Impact :** Aucune différence de contrat de réponse. OpenAPI peut afficher un type de réponse générique pour ces endpoints dans les deux cas.

### 7.4 Dépendances FastAPI

- **Legacy :** `Depends(get_current_user)` avec `User` et `get_current_user` importés depuis `security` ; pas d’autre dépendance déclarée.
- **Nouveau :** `Depends(get_current_user)` avec `User` et `get_current_user` importés depuis `app.core.security` et `app.modules.users.schemas.responses`. Même sémantique (auth obligatoire sur toutes les routes).

**Impact :** Aucune différence fonctionnelle pour l’appelant.

### 7.5 Schémas (body / response)

- **Legacy :** Import depuis `schemas.employee_exit` (fichier legacy, réexporte depuis le module si migration des schémas déjà faite).
- **Nouveau :** Import depuis `app.modules.employee_exits.schemas` (définitions locales du module).

Les noms et structures (EmployeeExitCreate, EmployeeExitUpdate, EmployeeExit, EmployeeExitWithDetails, ExitDocument, ExitDocumentCreate, DocumentUploadUrlRequest/Response, PublishExitDocumentsRequest/Response, StatusUpdateRequest, StatusTransitionResponse, ChecklistItem, ChecklistItemCreate, ChecklistItemUpdate, ExitDocumentDetails, ExitDocumentEditRequest, ExitDocumentEditResponse, ExitIndemnityCalculation) sont **alignés** entre legacy (via compat) et nouveau module.

**Impact :** Contrat d’API (body et response) identique.

### 7.6 Codes de statut

- **201 :** POST `/`, POST `/{exit_id}/documents`, POST `/{exit_id}/checklist` — identiques.
- **204 :** DELETE `/{exit_id}`, DELETE `/{exit_id}/documents/{document_id}`, DELETE `/{exit_id}/checklist/{item_id}` — identiques.
- **200 :** Toutes les autres routes — identiques.

**Aucune différence de codes de statut.**

---

## 8. Auth, permissions et guards (résumé)

| Route (résumé) | Legacy | Nouveau | Conforme |
|----------------|--------|---------|----------|
| POST `/` (create exit) | get_current_user ; company_id via employé ; check_user_has_exit_permission(..., 'create') | id. (get_current_user ; company_id via get_employee_company_id ; _check_exit_permission(..., 'create')) | Oui |
| GET `/` (list) | get_current_user ; company_id requis (400) ; check_user_has_exit_permission(..., 'view_all') | id. (_company_id_required ; _check_exit_permission(..., 'view_all')) | Oui |
| GET `/{exit_id}` | get_current_user ; company_id sans 400 | get_current_user ; _company_id_required (400 si absent) | Stricte (voir 7.1) |
| PATCH `/{exit_id}` | get_current_user | get_current_user ; _company_id_required | Stricte |
| PATCH `/{exit_id}/status` | get_current_user | get_current_user ; _company_id_required | Stricte |
| DELETE `/{exit_id}` | get_current_user ; company_id requis ; check_user_has_exit_permission(..., 'delete') | id. (_company_id_required ; _check_exit_permission(..., 'delete')) | Oui |
| POST calculate-indemnities | get_current_user | get_current_user ; _company_id_required | Stricte |
| Documents (upload-url, create, list, generate, delete, details, edit, history) | get_current_user ; company_id sans 400 (sauf si vérif interne) | get_current_user ; _company_id_required | Stricte |
| POST documents/publish | get_current_user ; company_id requis ; super_admin OU has_rh OU check_user_has_permission(..., 'employee_documents.publish_exit_documents') | id. (_company_id_required ; _check_publish_permission) | Oui |
| POST documents/.../unpublish | get_current_user ; company_id requis ; check_user_has_exit_permission(..., 'publish') OU check_user_has_permission(..., 'employee_exit.publish') | id. (_company_id_required ; _check_unpublish_permission) | Oui |
| Checklist (get, add, complete, delete) | get_current_user | get_current_user ; _company_id_required | Stricte |

Logique de permission (super_admin, admin/rh, publish/unpublish granulaire) est **reproduite** dans le nouveau router via les helpers ; seule la **obligation de company_id** est étendue à toutes les routes (amélioration de cohérence).

---

## 9. Tags et documentation

- **Préfixe :** `/api/employee-exits` — identique.
- **Tags :** `["Employee Exits"]` — identique.
- Les docstrings des endpoints sont présentes et équivalentes en sens (création, liste, détails, mise à jour, suppression, documents, checklist, etc.). Aucun impact sur le comportement HTTP ; utile pour OpenAPI / clients.

---

## 10. Route legacy encore nécessaire ?

- **Fonctionnellement :** Non. Le nouveau router couvre toutes les routes et reproduit le comportement métier et les permissions. La seule évolution est la généralisation du **400 si pas d’entreprise active** sur toutes les routes.
- **Compatibilité déploiement :** Tant que l’ancien système reste monté (ex. dans `main.py`), il peut servir de secours ou coexister avec le nouveau. Aucune suppression n’est requise pour cette vérification.

**Recommandation :** On peut considérer la migration des routes **complète** côté module. L’ancien router peut rester en place jusqu’à ce que le bootstrap applicatif (app/api/router) soit le point d’entrée unique et que les clients soient migrés ou validés.

---

## 11. Verdict final

- **Correspondance des routes :** 21/21 (toutes les routes legacy ont une route équivalente dans le nouveau router).
- **Routes manquantes :** Aucune.
- **Routes en trop :** Aucune.
- **Signatures (méthode, path, path params, query params, body, response_model, status_code) :** Conformes, à part la généralisation du 400 « Aucune entreprise active » (amélioration).
- **Auth :** Identique (get_current_user sur toutes les routes).
- **Permissions :** Équivalentes (create, view_all, delete, publish, unpublish) avec messages 403 éventuellement différents en texte uniquement.
- **Tags / préfixe :** Identiques.

**Verdict : migration complète conforme.**

La migration des routes employee_exits est **complète et conforme** au legacy. La seule évolution intentionnelle est l’obligation systématique d’une entreprise active (400 sur toutes les routes au lieu d’un sous-ensemble), ce qui renforce la cohérence sans casser le contrat pour les clients qui envoient déjà un contexte entreprise valide.
