# Vérification exhaustive des routes — module absences (legacy vs nouveau)

## 1. Liste des routes legacy (`api/routers/absences.py`)

| # | Méthode | Chemin (sans préfixe) | Path params | Query params | Body | Response model | Status codes | Auth / Dépendances | Tags |
|---|--------|------------------------|-------------|--------------|------|----------------|--------------|--------------------|------|
| 1 | POST | `/get-upload-url` | — | — | `filename` (Body embed=True) | SignedUploadURL | 200, 500 | `get_current_user` | Absences |
| 2 | POST | `/requests` | — | — | AbsenceRequestCreate | AbsenceRequest | 201, 400, 404, 500 | aucune | Absences |
| 3 | GET | `/` | — | `status` (Literal optional) | — | List[AbsenceRequestWithEmployee] | 200, 500 | aucune | Absences |
| 4 | PATCH | `/{request_id}` | request_id | — | AbsenceRequestStatusUpdate | AbsenceRequest | 200, 404, 500 | aucune | Absences |
| 5 | GET | `/employees/{employee_id}` | employee_id | — | — | List[AbsenceRequest] | 200, 500 | aucune | Absences |
| 6 | PATCH | `/requests/{request_id}/status` | request_id | — | AbsenceRequestStatusUpdate | AbsenceRequest | 200, 404, 500 | `get_current_user` | Absences |
| 7 | GET | `/employees/me/evenements-familiaux` | — | — | — | EvenementFamilialQuotaResponse | 200, 500 | `get_current_user` | Absences |
| 8 | GET | `/employees/me/balances` | — | — | — | AbsenceBalancesResponse | 200, 500* | `get_current_user` | Absences |
| 9 | GET | `/employees/me/calendar` | — | year, month | — | MonthlyCalendarResponse | 200, 500 | `get_current_user` | Absences |
| 10 | GET | `/employees/me/history` | — | — | — | List[AbsenceRequest] | 200, 500 | `get_current_user` | Absences |
| 11 | GET | `/employees/me/page-data` | — | year, month | — | AbsencePageData | 200, 404, 500 | `get_current_user` | Absences |
| 12 | POST | `/{absence_id}/generate-certificate` | absence_id | — | — | dict (certificate_id, message) | 200, 400, 404, 500 | `get_current_user` | Absences |
| 13 | GET | `/{absence_id}/certificate` | absence_id | — | — | dict (cert_data) | 200, 404, 500 | `get_current_user` | Absences |
| 14 | GET | `/{absence_id}/certificate/download` | absence_id | — | — | StreamingResponse (PDF) | 200, 404, 500 | `get_current_user` | Absences |

\* Legacy : en pratique toute exception (y compris un `HTTPException(404)` levé en interne pour « date d'embauche non trouvée ») est capturée par `except Exception` et renvoie 500 avec le message générique « Erreur lors du calcul des soldes. » — donc le legacy ne renvoie jamais 404 sur cette route.

**Préfixe legacy :** `prefix="/api/absences"` → routes exposées sous `/api/absences/...`.

---

## 2. Liste des routes du nouveau router (`app/modules/absences/api/router.py`)

| # | Méthode | Chemin (sans préfixe) | Path params | Query params | Body | Response model | Status codes | Auth / Dépendances | Tags |
|---|--------|------------------------|-------------|--------------|------|----------------|--------------|--------------------|------|
| 1 | POST | `/get-upload-url` | — | — | filename (Body(..., embed=True)) | SignedUploadURL | 200, 500 | get_current_user | Absences |
| 2 | POST | `/requests` | — | — | AbsenceRequestCreate | AbsenceRequest | 201, 400, 404, 500 | aucune | Absences |
| 3 | PATCH | `/requests/{request_id}/status` | request_id | — | AbsenceRequestStatusUpdate | AbsenceRequest | 200, 404, 500 | get_current_user | Absences |
| 4 | PATCH | `/{request_id}` | request_id | — | AbsenceRequestStatusUpdate | AbsenceRequest | 200, 404, 500 | aucune | Absences |
| 5 | GET | `/` | — | status (Literal optional) | — | List[AbsenceRequestWithEmployee] | 200, 500 | aucune | Absences |
| 6 | GET | `/employees/{employee_id}` | employee_id | — | — | List[AbsenceRequest] | 200, 500 | aucune | Absences |
| 7 | GET | `/employees/me/evenements-familiaux` | — | — | — | EvenementFamilialQuotaResponse | 200, 500 | get_current_user | Absences |
| 8 | GET | `/employees/me/balances` | — | — | — | AbsenceBalancesResponse | 200, 404, 500 | get_current_user | Absences |
| 9 | GET | `/employees/me/calendar` | — | year, month | — | MonthlyCalendarResponse | 200, 500 | get_current_user | Absences |
| 10 | GET | `/employees/me/history` | — | — | — | List[AbsenceRequest] | 200, 500 | get_current_user | Absences |
| 11 | GET | `/employees/me/page-data` | — | year, month | — | AbsencePageData | 200, 404, 500 | get_current_user | Absences |
| 12 | POST | `/{absence_id}/generate-certificate` | absence_id | — | — | dict (certificate_id, message) | 200, 400, 404, 500 | get_current_user | Absences |
| 13 | GET | `/{absence_id}/certificate/download` | absence_id | — | — | StreamingResponse (PDF) | 200, 404, 500 | get_current_user | Absences |
| 14 | GET | `/{absence_id}/certificate` | absence_id | — | — | dict (cert_data) | 200, 404, 500 | get_current_user | Absences |

**Préfixe nouveau :** `prefix="/api/absences"` → routes exposées sous `/api/absences/...`. Identique au legacy.

---

## 3. Correspondances exactes (legacy → nouveau)

| Legacy (méthode + chemin) | Nouveau (méthode + chemin) | Conforme |
|--------------------------|----------------------------|----------|
| POST /get-upload-url | POST /get-upload-url | Oui |
| POST /requests | POST /requests | Oui |
| GET / | GET / | Oui |
| PATCH /{request_id} | PATCH /{request_id} | Oui |
| GET /employees/{employee_id} | GET /employees/{employee_id} | Oui |
| PATCH /requests/{request_id}/status | PATCH /requests/{request_id}/status | Oui |
| GET /employees/me/evenements-familiaux | GET /employees/me/evenements-familiaux | Oui |
| GET /employees/me/balances | GET /employees/me/balances | Oui (voir §6) |
| GET /employees/me/calendar | GET /employees/me/calendar | Oui |
| GET /employees/me/history | GET /employees/me/history | Oui |
| GET /employees/me/page-data | GET /employees/me/page-data | Oui |
| POST /{absence_id}/generate-certificate | POST /{absence_id}/generate-certificate | Oui |
| GET /{absence_id}/certificate | GET /{absence_id}/certificate | Oui |
| GET /{absence_id}/certificate/download | GET /{absence_id}/certificate/download | Oui |

Toutes les routes legacy ont une route équivalente dans le nouveau router (même méthode, même chemin, même préfixe).

---

## 4. Routes manquantes

**Aucune.** Chaque endpoint du legacy a un équivalent dans le nouveau module.

---

## 5. Routes en trop

**Aucune.** Le nouveau router n’expose que des routes qui existent déjà dans le legacy.

---

## 6. Différences de signature ou de comportement HTTP

### 6.1 GET `/employees/me/balances` — code de statut quand la date d’embauche est absente

- **Legacy :** En interne, lève `HTTPException(404, "Date d'embauche non trouvée pour l'employé.")` si pas de `hire_date`, mais le bloc `except Exception as e` capture toute exception (y compris cette `HTTPException`) et renvoie systématiquement **500** avec le message « Erreur lors du calcul des soldes. ». Donc le client reçoit toujours **500** dans ce cas.
- **Nouveau :** `LookupError` (ex. « Date d'embauche non trouvée pour l'employé. ») est traduit en **404** avant le `except Exception` générique.
- **Impact :** Le nouveau comportement est plus cohérent (404 = ressource/contexte non trouvé). C’est une **divergence volontaire** par rapport au legacy (correction de bug). Les clients qui s’appuyaient sur un 500 dans ce cas verront désormais un 404.

### 6.2 Ordre de déclaration des routes

- L’ordre des décorateurs diffère (ex. dans le nouveau router, `PATCH /requests/{request_id}/status` est déclaré avant `PATCH /{request_id}` pour éviter que `requests` soit capturé comme `request_id`). Aucun impact sur les URLs ou le comportement documenté, uniquement sur la résolution FastAPI des chemins.

### 6.3 Corps POST `/get-upload-url`

- Legacy : `filename: Annotated[str, Body(embed=True)]`.
- Nouveau : `filename: str = Body(..., embed=True)`.
- Comportement HTTP identique : body JSON `{"filename": "..."}` dans les deux cas.

### 6.4 Réponses non typées (dict)

- `POST /{absence_id}/generate-certificate` : les deux renvoient un dict `{"certificate_id": ..., "message": ...}` sans `response_model` déclaré.
- `GET /{absence_id}/certificate` : les deux renvoient un dict (cert_data) sans `response_model` déclaré.

Aucune différence de contrat.

---

## 7. Préfixes et paths dynamiques

- **Préfixe :** `/api/absences` — identique legacy / nouveau.
- **Paths dynamiques :**
  - `request_id` (PATCH `/{request_id}` et PATCH `/requests/{request_id}/status`) : même nom, même sémantique.
  - `employee_id` (GET `/employees/{employee_id}`) : identique.
  - `absence_id` (POST/GET `/{absence_id}/...`) : identique.

Aucune différence.

---

## 8. Paramètres de query

- GET `/` : `status` (optional Literal['pending','validated','rejected','cancelled']) — identique.
- GET `/employees/me/calendar` : `year`, `month` (int) — identique.
- GET `/employees/me/page-data` : `year`, `month` (int) — identique.

Aucune différence.

---

## 9. Body models

- AbsenceRequestCreate (POST /requests) : même schéma (réexporté depuis le module).
- AbsenceRequestStatusUpdate (PATCH) : même schéma.
- filename embed (POST /get-upload-url) : même usage.

Aucune différence de contrat.

---

## 10. Response models

- SignedUploadURL, AbsenceRequest, AbsenceRequestWithEmployee, AbsenceBalancesResponse, MonthlyCalendarResponse, AbsencePageData, EvenementFamilialQuotaResponse, List[AbsenceRequest], dict, StreamingResponse : tous présents et alignés (schémas du module réexportés ou identiques).

Aucune différence.

---

## 11. Dépendances FastAPI et auth

- **Legacy :** `from security import get_current_user, User` ; `User = Depends(get_current_user)` sur les routes « me » et certificats.
- **Nouveau :** `from app.core.security import get_current_user` ; `User` depuis `app.modules.users.schemas.responses` ; même usage de `Depends(get_current_user)` sur les mêmes routes.

Routes sans auth (identiques) : POST /requests, GET /, PATCH /{request_id}, GET /employees/{employee_id}.  
Routes avec auth (identiques) : POST /get-upload-url, PATCH /requests/{request_id}/status, GET /employees/me/*, POST /{absence_id}/generate-certificate, GET /{absence_id}/certificate, GET /{absence_id}/certificate/download.

Aucune route legacy protégée ne devient publique dans le nouveau router, et inversement.

---

## 12. Tags

- Legacy : `tags=["Absences"]` sur le routeur.
- Nouveau : `tags=["Absences"]`.

Documentation OpenAPI inchangée pour le groupe « Absences ».

---

## 13. Routes legacy encore nécessaires

- Tant que le point d’entrée (ex. `main.py`) inclut encore `api/routers/absences.py`, les **deux** jeux de routes coexistent (même préfixe `/api/absences`). Pour éviter doublons et ambiguïté, il faut à terme **désactiver ou retirer** l’inclusion du router legacy dès que le front (ou les clients) utilisent uniquement le nouveau module.
- Si l’ancien router est retiré, **aucune route legacy n’est nécessaire** : le nouveau router couvre tous les endpoints avec le même contrat (à l’exception du 404 vs 500 sur `/employees/me/balances` documenté ci‑dessus).

---

## 14. Verdict final

- **Migration complète** : tous les endpoints legacy sont présents dans le nouveau router (méthode, préfixe, chemin, path/query/body, response, auth, tags).
- **Une divergence de comportement HTTP** : GET `/employees/me/balances` renvoie **404** (au lieu de 500) lorsque la date d’embauche est absente ; le nouveau comportement est plus correct et plus RESTful.

**Verdict explicite : migration complète conforme**, avec une amélioration volontaire du comportement (404 au lieu de 500 pour « date d’embauche non trouvée » sur `/employees/me/balances`). Aucune route manquante, aucune route en trop. L’ancien système peut être retiré une fois les clients alignés sur le nouveau router ; jusqu’à ce retrait, garder le legacy pour compatibilité si besoin, en évitant de monter les deux routers sur le même préfixe en production.
