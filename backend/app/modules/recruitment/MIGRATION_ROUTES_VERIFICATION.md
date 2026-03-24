# Vérification exhaustive des routes — module Recruitment

Comparaison stricte entre le router legacy (`api/routers/recruitment.py`) et le nouveau router (`app/modules/recruitment/api/router.py`).

---

## 1. Liste des routes LEGACY

| # | Méthode | Chemin relatif (sous prefix) | Path params | Query params | Body | Response | Auth / Guards |
|---|--------|------------------------------|-------------|--------------|------|----------|----------------|
| 1 | GET | `/settings` | — | — | — | `{"enabled": bool}` | get_current_user ; pas de company → 200 `enabled: false` |
| 2 | GET | `/jobs` | — | `status` (opt) | — | `List[JobOut]` | module_enabled + RH |
| 3 | POST | `/jobs` | — | — | JobCreate | JobOut | module_enabled + RH |
| 4 | PATCH | `/jobs/{job_id}` | job_id | — | JobUpdate | JobOut | module_enabled + RH |
| 5 | GET | `/jobs/{job_id}/stages` | job_id | — | — | `List[PipelineStageOut]` | module_enabled (RH ou Collab) |
| 6 | GET | `/candidates` | — | job_id, stage_id, search (opt) | — | `List[CandidateOut]` | module_enabled ; filtre participant si non RH |
| 7 | POST | `/candidates` | — | — | CandidateCreate | CandidateOut | module_enabled + RH |
| 8 | GET | `/candidates/{candidate_id}` | candidate_id | — | — | CandidateOut | module_enabled + Collab ou RH (participant) |
| 9 | PATCH | `/candidates/{candidate_id}` | candidate_id | — | CandidateUpdate | CandidateOut | module_enabled + RH |
| 10 | DELETE | `/candidates/{candidate_id}` | candidate_id | — | — | `{"ok": true}` | module_enabled + RH |
| 11 | POST | `/candidates/{candidate_id}/move` | candidate_id | — | MoveCandidateBody | `{"ok": true, "stage": ...}` | module_enabled + RH |
| 12 | POST | `/candidates/{candidate_id}/check-duplicate` | candidate_id | — | — | `{"warnings": [DuplicateWarning]}` | module_enabled + RH |
| 13 | POST | `/candidates/{candidate_id}/hire` | candidate_id | — | HireCandidateBody | `{"ok": true, "employee_id": ..., "message": ...}` | module_enabled + RH |
| 14 | GET | `/interviews` | — | candidate_id (opt) | — | `List[InterviewOut]` | module_enabled ; filtre participant si non RH |
| 15 | POST | `/interviews` | — | — | InterviewCreate | InterviewOut | module_enabled + RH |
| 16 | PATCH | `/interviews/{interview_id}` | interview_id | — | InterviewUpdate | `{"ok": true}` | module_enabled ; RH ou Collab (summary only) |
| 17 | GET | `/notes` | — | candidate_id (requis) | — | `List[NoteOut]` | module_enabled + Collab ou RH (participant) |
| 18 | POST | `/notes` | — | — | NoteCreate | NoteOut | module_enabled + Collab ou RH (participant) |
| 19 | GET | `/opinions` | — | candidate_id (requis) | — | `List[OpinionOut]` | module_enabled + Collab ou RH (participant) |
| 20 | POST | `/opinions` | — | — | OpinionCreate | OpinionOut | module_enabled + Collab ou RH (participant) |
| 21 | GET | `/timeline` | — | candidate_id (requis) | — | `List[TimelineEventOut]` | module_enabled + Collab ou RH (participant) |
| 22 | GET | `/rejection-reasons` | — | — | — | `{"reasons": [...]}` | module_enabled |

**Prefix legacy :** `prefix="/api/recruitment"` (défini dans le router).  
**Tags legacy :** `tags=["Recruitment"]`.

---

## 2. Liste des routes NOUVEAU ROUTER

| # | Méthode | Chemin relatif | Path params | Query params | Body | Response | Auth / Guards |
|---|--------|----------------|-------------|--------------|------|----------|----------------|
| 1 | GET | `/settings` | — | — | — | `{"enabled": bool}` | get_current_user ; pas company → `enabled: false` |
| 2 | GET | `/jobs` | — | `status` (opt) | — | `List[JobOut]` | module_enabled + RH |
| 3 | POST | `/jobs` | — | — | JobCreate | JobOut | module_enabled + RH |
| 4 | PATCH | `/jobs/{job_id}` | job_id | — | JobUpdate | JobOut | module_enabled + RH |
| 5 | GET | `/jobs/{job_id}/stages` | job_id | — | — | `List[PipelineStageOut]` | module_enabled |
| 6 | GET | `/candidates` | — | job_id, stage_id, search (opt) | — | `List[CandidateOut]` | module_enabled ; participant_user_id si non RH |
| 7 | POST | `/candidates` | — | — | CandidateCreate | CandidateOut | module_enabled + RH |
| 8 | GET | `/candidates/{candidate_id}` | candidate_id | — | — | CandidateOut | module_enabled + Collab ou RH |
| 9 | PATCH | `/candidates/{candidate_id}` | candidate_id | — | CandidateUpdate | CandidateOut | module_enabled + RH |
| 10 | DELETE | `/candidates/{candidate_id}` | candidate_id | — | — | `{"ok": true}` | module_enabled + RH |
| 11 | POST | `/candidates/{candidate_id}/move` | candidate_id | — | MoveCandidateBody | `{"ok": true, "stage": ...}` | module_enabled + RH |
| 12 | POST | `/candidates/{candidate_id}/check-duplicate` | candidate_id | — | — | `{"warnings": [...]}` | module_enabled + RH |
| 13 | POST | `/candidates/{candidate_id}/hire` | candidate_id | — | HireCandidateBody | `{"ok": true, "employee_id": ..., "message": ...}` | module_enabled + RH |
| 14 | GET | `/interviews` | — | candidate_id (opt) | — | `List[InterviewOut]` | module_enabled ; participant_user_id si non RH |
| 15 | POST | `/interviews` | — | — | InterviewCreate | InterviewOut | module_enabled + RH |
| 16 | PATCH | `/interviews/{interview_id}` | interview_id | — | InterviewUpdate | `{"ok": true}` | module_enabled ; is_rh pour champs modifiables |
| 17 | GET | `/notes` | — | candidate_id (requis) | — | `List[NoteOut]` | module_enabled + Collab ou RH |
| 18 | POST | `/notes` | — | — | NoteCreate | NoteOut | module_enabled + Collab ou RH |
| 19 | GET | `/opinions` | — | candidate_id (requis) | — | `List[OpinionOut]` | module_enabled + Collab ou RH |
| 20 | POST | `/opinions` | — | — | OpinionCreate | OpinionOut | module_enabled + Collab ou RH |
| 21 | GET | `/timeline` | — | candidate_id (requis) | — | `List[TimelineEventOut]` | module_enabled + Collab ou RH |
| 22 | GET | `/rejection-reasons` | — | — | — | `{"reasons": [...]}` | module_enabled |

**Prefix nouveau :** `prefix="/api/recruitment"`.  
**Tags nouveau :** `tags=["Recruitment"]`.

---

## 3. Correspondances exactes (legacy → nouveau)

| Legacy (méthode + chemin) | Nouveau (méthode + chemin) | Conforme |
|---------------------------|----------------------------|----------|
| GET /settings | GET /settings | Oui |
| GET /jobs | GET /jobs | Oui |
| POST /jobs | POST /jobs | Oui |
| PATCH /jobs/{job_id} | PATCH /jobs/{job_id} | Oui |
| GET /jobs/{job_id}/stages | GET /jobs/{job_id}/stages | Oui |
| GET /candidates | GET /candidates | Oui |
| POST /candidates | POST /candidates | Oui |
| GET /candidates/{candidate_id} | GET /candidates/{candidate_id} | Oui |
| PATCH /candidates/{candidate_id} | PATCH /candidates/{candidate_id} | Oui |
| DELETE /candidates/{candidate_id} | DELETE /candidates/{candidate_id} | Oui |
| POST /candidates/{candidate_id}/move | POST /candidates/{candidate_id}/move | Oui |
| POST /candidates/{candidate_id}/check-duplicate | POST /candidates/{candidate_id}/check-duplicate | Oui |
| POST /candidates/{candidate_id}/hire | POST /candidates/{candidate_id}/hire | Oui |
| GET /interviews | GET /interviews | Oui |
| POST /interviews | POST /interviews | Oui |
| PATCH /interviews/{interview_id} | PATCH /interviews/{interview_id} | Oui |
| GET /notes | GET /notes | Oui |
| POST /notes | POST /notes | Oui |
| GET /opinions | GET /opinions | Oui |
| POST /opinions | POST /opinions | Oui |
| GET /timeline | GET /timeline | Oui |
| GET /rejection-reasons | GET /rejection-reasons | Oui |

**Toutes les 22 routes legacy ont une route correspondante dans le nouveau router (même méthode, même chemin relatif).**

---

## 4. Routes manquantes (dans le nouveau)

**Aucune.** Toutes les routes du legacy sont présentes dans le nouveau router.

---

## 5. Routes en trop (dans le nouveau)

**Aucune.** Le nouveau router n’expose que des routes qui existent dans le legacy.

---

## 6. Différences de signature ou de comportement HTTP

### 6.1 Prefix et tags

- **Prefix :** identique (`/api/recruitment`) sur les deux routers.
- **Tags :** identiques (`["Recruitment"]`). Comportement documentaire (OpenAPI) aligné.

### 6.2 Path / Query / Body

- **Path params :** mêmes noms (`job_id`, `candidate_id`, `interview_id`) et mêmes positions dans le chemin.
- **Query params :** identiques — `status` (opt), `job_id`, `stage_id`, `search` (opt), `candidate_id` (requis pour notes/opinions/timeline).
- **Body models :** les schémas du module (`app/modules/recruitment/schemas`) sont alignés sur le legacy (JobCreate, JobUpdate, CandidateCreate, etc.). Aucune différence de contrat.

### 6.3 Response models

- Réponses typées (`JobOut`, `CandidateOut`, etc.) et réponses dict (`{"ok": true}`, `{"enabled": ...}`, `{"warnings": [...]}`, `{"reasons": [...]}`) identiques entre legacy et nouveau.

### 6.4 Codes de statut et erreurs

| Contexte | Legacy | Nouveau | Conforme ? |
|----------|--------|---------|------------|
| Pas d’entreprise active | 400 "Aucune entreprise active" | 400 idem | Oui |
| Module désactivé | 403 "Le module Recrutement n'est pas activé..." | 403 idem | Oui |
| Pas droit RH / pas participant | 403 "Vous n'avez pas l'autorisation..." | 403 idem | Oui |
| Poste / Candidat / Étape / Entretien non trouvé | 404 + message | 404 idem (via _value_error_to_http) | Oui |
| Aucune modification | 400 "Aucune modification" | 400 idem | Oui |
| Suppression candidat avancé | 400 "Impossible de supprimer..." | 400 idem | Oui |
| Motif refus manquant | 400 "Un motif de refus est obligatoire." | 400 idem | Oui |
| Embauche champs manquants | 400 "Impossible de finaliser l'embauche..." | 400 idem | Oui |
| Valeur erreur (ex. create_employee_from_candidate) | 400 detail=str(e) | 400 detail=str(e) | Oui |
| Collab update interview (autre que summary) | 403 "Accès non autorisé" | 403 idem | Oui |
| Avis rating invalide | 400 "L'avis doit être 'favorable' ou 'defavorable'." | 400 idem (via application) | Oui |
| **Erreur création poste** (insert échoue) | **500** "Erreur lors de la création du poste" | **400** (ValueError mappé en 400) | **Non** |
| **Erreur création candidat** (insert échoue) | **500** "Erreur lors de la création du candidat" | **400** (ValueError mappé en 400) | **Non** |
| **Erreur création entretien** (insert échoue) | **500** "Erreur lors de la création de l'entretien" | **400** (ValueError mappé en 400) | **Non** |
| **Erreur création note / avis** (insert échoue) | **500** "Erreur" | **400** (ValueError mappé en 400) | **Non** |

**Divergence :** en legacy, les échecs d’insertion (poste, candidat, entretien, note, avis) lèvent **HTTP 500**. Dans le nouveau router, toute `ValueError` non « non trouvé » / « Accès non autorisé » est transformée en **HTTP 400**. Donc dans ces cas d’échec technique d’écriture, le code de statut passe de 500 à 400.

### 6.5 Dépendances FastAPI

- **Legacy :** `Depends(get_current_user)`, `User`, schémas locaux (définis dans le fichier).
- **Nouveau :** `Depends(get_current_user)`, `User` (via `security`), schémas importés depuis `app.modules.recruitment.schemas`. Comportement équivalent pour l’API.

### 6.6 Permissions / guards / auth

- **Legacy :** `_ensure_module_enabled`, `_ensure_rh_access`, `_ensure_collab_or_rh` ; `get_recruitment_setting` et `is_user_participant_for_candidate` depuis le service legacy.
- **Nouveau :** mêmes gardes (mêmes messages 400/403), `get_recruitment_setting` et `is_user_participant_for_candidate` fournis par l’application du module. Même sémantique : module activé, RH vs Collab, participant sur le candidat.

---

## 7. Route legacy encore nécessaire

- **Oui, tant que la compatibilité est requise.**  
  Le legacy (`api/routers/recruitment.py`) est encore monté dans l’ancien point d’entrée (`main.py`). Si l’application est servie uniquement par `app.main:app` et que le router global `app.api.router` inclut le **nouveau** router recruitment, alors les appels clients vers `/api/recruitment/*` sont servis par le nouveau code.  
  Dans ce cas, **on peut considérer que la route legacy n’est plus nécessaire** une fois la bascule effectuée et validée.  
  Si au contraire l’ancien `main.py` reste en usage (ou utilisé en parallèle), **il faut conserver le legacy** jusqu’à arrêt complet de l’ancien point d’entrée.

---

## 8. Verdict final

- **Toutes les routes legacy sont migrées** (22/22), avec les mêmes méthodes, chemins, path/query/body et la même sémantique d’auth/guards.
- **Une divergence existe** sur les **codes de statut** en cas d’échec d’insertion (poste, candidat, entretien, note, avis) : **500 en legacy**, **400 en nouveau**.

**Verdict : migration incomplète (divergence de codes HTTP).**

Pour atteindre une **migration complète conforme**, il faudrait soit :
- dans le nouveau router (ou dans la couche application), distinguer « erreur de validation / requête invalide » (400) et « erreur serveur / échec persistance » (500) et renvoyer 500 pour les messages du type « Erreur lors de la création du poste/candidat/entretien » et « Erreur » (notes/avis),  
soit  
- acter que ces cas sont traités comme des erreurs client (400) dans la nouvelle API et documenter ce changement par rapport au legacy.

---

*Document généré pour vérification de la migration du module recruitment. Aucun fichier n’a été modifié.*
