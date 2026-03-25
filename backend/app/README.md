# Application API SIRH — point d'entrée modulaire (`app/`)

Ce répertoire est le **nouveau point d'entrée** de l'API backend du SIRH. Il met en œuvre une architecture **modular monolith** : une seule application FastAPI, organisée en modules métier autonomes et en couches claires (API → Application → Domain → Infrastructure).

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Structure des répertoires](#3-structure-des-répertoires)
4. [Fonctionnement](#4-fonctionnement)
5. [Conventions de code](#5-conventions-de-code)
6. [Démarrage et tests](#6-démarrage-et-tests)

---

## 1. Vue d'ensemble

### Objectif

- **Point d'entrée unique** : l'application FastAPI est exposée via **`app.main:app`** (`backend/app/main.py`). C’est le point d’entrée supporté en production et en développement.
- **Modularité** : chaque domaine métier (auth, employés, paie, absences, etc.) vit dans un **module** (`app/modules/<nom>/`) avec ses propres couches (api, application, domain, infrastructure, schemas).
- **Pas de couplage direct entre modules** : la communication se fait via interfaces, schémas partagés ou (à terme) événements. Les imports croisés de détail entre modules sont évités.

### Principes

- **Core** et **shared** : configuration, sécurité, base de données et briques transverses (PDF, email, storage, etc.) — pas de logique métier spécifique à un domaine.
- **Un module = un domaine** : responsabilités bien délimitées, dépendances explicites et documentées.

---

## 2. Architecture

### Schéma global

```
app/
├── main.py                 # Point d'entrée FastAPI (CORS, health, montage du router global)
├── api/                    # Agrégation HTTP
│   └── router.py           # Inclut tous les routers des modules (prefix, tags)
├── core/                   # Config, DB, sécurité, chemins, logging
├── shared/                 # Briques transverses (kernel, schemas, utils, infrastructure)
└── modules/                # Un dossier par domaine métier
    └── <module>/
        ├── api/            # Router(s) FastAPI du module
        ├── application/   # Cas d'usage (commands, queries, services)
        ├── domain/         # Entités, règles métier, interfaces (ports)
        ├── infrastructure/ # Repositories, providers, mappers, requêtes
        └── schemas/        # Requêtes / réponses Pydantic du module
```

### Flux d'une requête

1. **Entrée HTTP** → `main.py` → `api/router.py` → router du module (ex. `modules/absences/api/router.py`).
2. **API (router)** : validation des entrées (schémas Pydantic), résolution des dépendances (ex. `get_current_user`), appel à la couche **application** (commands/queries). Gestion des erreurs (ValueError → 400, LookupError → 404, etc.) et retour HTTP.
3. **Application** : orchestration du cas d'usage ; appelle le **domain** (règles, entités) et l'**infrastructure** (repositories, providers). Pas d'accès HTTP ni de logique de réponse brute ici.
4. **Domain** : règles métier pures, entités, value objects, interfaces (ports). Aucun accès base de données ni FastAPI.
5. **Infrastructure** : implémentations des ports (repositories Supabase, providers, mappers), requêtes et appels externes.

### Règles de dépendance

- **API** → application, schemas, core (security).
- **Application** → domain, infrastructure, schemas (DTO / requêtes).
- **Domain** → rien en dehors de `shared/kernel` ou types purs si besoin.
- **Infrastructure** → domain (interfaces), core (database, paths), shared.

Les modules ne s'importent pas entre eux pour des détails d'implémentation ; les dépendances explicites (ex. `users` pour `auth`) sont documentées.

---

## 3. Structure des répertoires

### `main.py`

- Création de l'instance FastAPI (titre, version).
- CORS : origines autorisées (localhost, front déployé).
- Montage du routeur global : `app.include_router(api_router)`.
- Route `/health` pour healthcheck.
- Emplacements réservés pour lifecycle (startup/shutdown) et exception handlers.

### `api/`

- **`router.py`** : agrège tous les routers des modules. Chaque module expose un (ou plusieurs) `APIRouter` ; ils sont inclus avec `include_router` en précisant préfixe et tags. Les préfixes sont du type `/api/auth`, `/api/absences`, etc., pour garder la compatibilité avec le front et l'ancien point d'entrée.

### `core/`

| Fichier / rôle | Description |
|----------------|-------------|
| **Config / settings** | Variables d'environnement (Supabase, clés service), `require_supabase_env()`, `get_supabase_admin_env()`. |
| **database** | Client Supabase par défaut (`supabase`), `get_supabase_client()`, `get_supabase_admin_client()`. Source de vérité pour l'accès DB. |
| **security** | `oauth2_scheme`, `get_current_user`, `get_current_user_role` ; validation JWT, chargement du profil et des accès multi-entreprises, contexte entreprise active (header `X-Active-Company`). |
| **paths** | Chemins du moteur de paie (`PAYROLL_ENGINE_ROOT`, `payroll_engine_root()`, `payroll_engine_data()`, etc.). Pas de chemins en dur ailleurs. |
| **logging** | Logger racine `app`, `get_logger()`, `configure_logging()`. |

### `shared/`

- **kernel** : types transverses, `Result` (Ok/Err) pour les opérations sans lever d'exception.
- **schemas** : schémas Pydantic partagés (pagination, envelope, signed_url, base).
- **utils** : helpers (export, texte, IBAN, dates, ids).
- **infrastructure** : PDF, email, storage, AI, exports, etc. — tout ce qui est utilisé par plusieurs modules sans appartenir à un domaine.
- **compat** : couche de compatibilité avec l'ancien code (ex. document generator) pendant la migration.

### `modules/`

Un répertoire par domaine. Noms en snake_case (ex. `annual_reviews`, `company_groups`, `repos_compensateur`). Liste des modules avec router API :

- access_control, absences, annual_reviews, auth, bonus_types, companies, contract_parser, copilot, collective_agreements, company_groups, cse, dashboard, employees, employee_exits, exports, expenses, medical_follow_up, monthly_inputs, mutuelle_types, participation, payslips, payroll (sous-jacent à payslips), promotions, rates, recruitment, repos_compensateur, residence_permits, rib_alerts, saisies_avances, schedules, scraping, super_admin, uploads, users.

Structure type d'un module :

```
modules/<module>/
├── api/
│   ├── __init__.py
│   ├── router.py          # Définition des routes et dépendances FastAPI
│   └── dependencies.py    # Optionnel : dépendances injectées (ex. repo)
├── application/
│   ├── commands.py        # Cas d'usage écriture (create, update, delete)
│   ├── queries.py        # Cas d'usage lecture (list, get by id)
│   ├── service.py        # Optionnel : orchestration plus riche
│   └── dto.py            # Optionnel : objets de transfert internes
├── domain/
│   ├── entities.py       # Entités métier (dataclasses ou modèles)
│   ├── value_objects.py  # Objets valeur
│   ├── enums.py          # Énumérations métier
│   ├── rules.py          # Règles métier pures (sans I/O)
│   └── interfaces.py     # Ports (abstract base classes) pour l'infra
├── infrastructure/
│   ├── repository.py     # Implémentation des interfaces de persistance
│   ├── providers.py      # Fourniture de données externes (ex. catalogue)
│   ├── queries.py        # Requêtes métier complexes
│   └── mappers.py        # Conversion entité ↔ dict / row DB
└── schemas/
    ├── requests.py       # Schémas Pydantic entrée API
    ├── responses.py      # Schémas Pydantic sortie API
    └── __init__.py       # Réexport pour import propre
```

---

## 4. Fonctionnement

### Démarrage de l'application

Depuis la racine de **`backend/`** (répertoire courant = racine du package `app`) :

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

En production (sans reload, avec workers) :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Agrégation des routes

- `app.main` crée l’app et inclut `app.api.router`.
- `app.api.router` importe chaque router de module et fait `include_router(..., prefix=..., tags=[...])`. Les préfixes sont définis soit dans le router du module, soit dans l’appel à `include_router`. Les URLs finales restent alignées avec l’ancien API (ex. `/api/absences`, `/api/company`, `/api/medical-follow-up`).

### Authentification et contexte

- **JWT** : schéma OAuth2 (`tokenUrl="/api/auth/login"`). Les routes protégées utilisent `Depends(get_current_user)`.
- **Utilisateur courant** : `get_current_user` valide le token via Supabase Auth, charge le profil et les accès multi-entreprises, et gère l’entreprise active (header `X-Active-Company`). Le contexte RLS / session peut être défini via RPC Supabase si nécessaire.
- Les permissions métier fines (ex. « droit RH », « droit admin entreprise ») restent dans les routers ou dans les modules, pas dans `core.security`.

### Base de données

- **Client par défaut** : `from app.core.database import supabase`. Utilisé par les repositories et les requêtes dans les modules.
- **Client admin** : `get_supabase_admin_client()` pour les opérations qui contournent les RLS (création utilisateur, super admin, etc.). Les variables d’environnement sont lues via `app.core.settings`.

### Chemins et moteur de paie

- Tous les chemins critiques (moteur de paie, data, templates) passent par `app.core.paths`. Aucun chemin en dur dans les modules. `PAYROLL_ENGINE_ROOT` (alias `PATH_TO_PAYROLL_ENGINE`) pointe vers `app/runtime/payroll/` (données et templates à l’exécution).

---

## 5. Conventions de code

### Imports

- **Préfixe `app.`** : tous les imports internes à l’application utilisent le package `app` (ex. `from app.core.security import get_current_user`, `from app.modules.absences.application import commands`). Exécuter uvicorn et pytest avec `backend/` comme répertoire de travail (voir `pytest.ini` : `pythonpath = .`).
- **Éviter les imports circulaires** : les routers n’importent que application + schemas + core ; l’application n’importe pas les routers.

### Nommage

- **Modules** : snake_case (`annual_reviews`, `company_groups`, `repos_compensateur`).
- **Fichiers** : snake_case (`router.py`, `commands.py`, `value_objects.py`).
- **Classes** : PascalCase. Repositories : suffixe cohérent (ex. `SupabaseMonthlyInputsRepository`) ou nom de classe + `Repository` / `Provider`.
- **Routes** : kebab-case dans les URLs (ex. `/api/medical-follow-up`, `/get-upload-url`).

### Couche API (routers)

- Responsabilité : valider l’entrée (schémas), résoudre les dépendances (user, company), appeler **une** commande ou requête application, traduire les exceptions en HTTP (400, 404, 500) et retourner les schémas de réponse.
- Pas de logique métier ni d’accès direct à Supabase dans le router ; toute la logique est dans application/domain/infrastructure.
- Gestion d’erreurs : une fonction locale type `_handle_application_errors(e)` qui lève `HTTPException` selon le type d’exception (ValueError → 400, LookupError → 404, etc.) est recommandée.

### Couche Application

- **Commands** : création, mise à jour, suppression ; retournent des DTO ou des dict pour que le router construise la réponse.
- **Queries** : lecture (liste, détail) ; retournent des objets ou des structures typées.
- Les commandes/queries délèguent au **domain** (règles) et à l’**infrastructure** (repositories, providers). Pas d’import de FastAPI ni de construction de réponse HTTP.

### Couche Domain

- **Règles** : fonctions pures ou classes sans I/O ; toutes les données passent en paramètres.
- **Entités** : dataclasses ou modèles métier ; pas de dépendance à la base ni à Pydantic (sauf si value object simple).
- **Interfaces** : ABC définissant les ports (ex. `IMonthlyInputsRepository`) ; implémentations uniquement dans infrastructure.

### Couche Infrastructure

- **Repositories** : implémentent les interfaces du domain ; utilisent `app.core.database.supabase` (ou `get_supabase_admin_client()` si besoin).
- **Providers / queries** : requêtes métier plus complexes, mappers row → entité ou → dict. Les noms de tables et colonnes restent centralisés ici.

### Schémas (schemas/)

- **requests** : modèles Pydantic pour le body et les query params des endpoints (validation entrante).
- **responses** : modèles Pydantic pour les réponses (sérialisation sortante). Réexport dans `schemas/__init__.py` pour des imports propres depuis les routers.

### Résultat et erreurs

- Pour les cas d’usage qui évitent les exceptions, utiliser `shared.kernel.result` : `Ok(value)` / `Err(error)`, avec `is_ok()` / `is_err()`. Le router peut alors convertir `Err` en `HTTPException`.

### Logging

- Utiliser `app.core.logging.get_logger(__name__)` pour les logs structurés. Éviter les `print()` pour la logique (les garder uniquement en debug temporaire si besoin).

---

## 6. Démarrage et tests

### Lancer l’API

À la racine de `backend/` :

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Vérifier : `GET http://localhost:8000/health` → `{"status":"ok"}`.

### Tests

- Les tests d’intégration et E2E utilisent `from app.main import app` et le `TestClient` FastAPI sur `app`.
- Le répertoire de tests est à la racine de `backend/` (`tests/`), pas dans `app/`. Les conventions de nommage et d’import ci-dessus s’appliquent aussi aux tests qui ciblent les modules de `app`.
- Vérification d’architecture (imports), si configuré :

```bash
cd backend
lint-imports --config .importlinter
```

Cette commande échoue si un module enfreint les contrats de couches (API/Application/Infrastructure/Domain) ou si `domain` importe des couches interdites.

---

## Références

- **Documentation générale du backend** : [README.md](../README.md) (dossier `backend/`)
- **Tests** : [tests/README.md](../tests/README.md)
