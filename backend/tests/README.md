# Tests — Backend API

Ce document décrit l’**architecture**, le **fonctionnement** et les **conventions de code** des tests du backend API.

---

## 1. Architecture des tests

Les tests sont organisés en **quatre niveaux** et suivent la structure des modules applicatifs (`app.modules.*`).

```
tests/
├── conftest.py              # Fixtures et configuration pytest partagés
├── fixtures/                # Données et helpers partagés (fixtures réutilisables)
├── migration/               # Fixtures pour comparaison payroll / migrations
├── unit/                     # Tests unitaires (logique isolée, mocks)
│   ├── core/                 # Ex. chemins runtime (`app.core.paths`, paie)
│   └── <module>/             # Un dossier par module (employees, auth, payroll, …)
│       ├── test_domain.py    # Règles métier, value objects, constantes
│       ├── test_service.py   # Services applicatifs
│       ├── test_commands.py  # Commandes (écritures)
│       └── test_queries.py   # Queries (lectures)
├── integration/              # Tests d’intégration (API, repository, wiring)
│   └── <module>/
│       ├── test_api.py       # Routes HTTP (TestClient, auth, status codes)
│       ├── test_repository.py # Repository + Supabase (mock ou DB de test)
│       └── test_wiring.py    # Câblage module (dépendances, flux)
└── e2e/                      # Tests bout en bout / smoke
    ├── test_smoke_global.py   # Démarrage app, health, openapi, auth
    ├── test_smoke_modules.py  # Un appel HTTP minimal par module
    ├── test_auth_flow.py     # Flux login / me
    └── cross_module/         # Parcours métier multi-modules
        └── test_cross_flows.py
```

### Rôle de chaque niveau

| Niveau        | Objectif | DB / HTTP | Mocks |
|---------------|----------|-----------|--------|
| **Unit**      | Logique métier et application en isolation | Non | Oui (repositories, providers) |
| **Integration** | Routes API, repositories, wiring | Optionnel (DB de test ou mocks) | Oui pour API (dependency_overrides, patch) |
| **E2E**       | Smoke et parcours réels (auth, health, un appel par module) | Optionnel | Non (client HTTP réel, auth optionnelle) |

### Scripts à la racine de `tests/` (`test_*.py`, `test_*_complet.py`)

Ce sont des **smoke / démos manuelles** (souvent avec Supabase réel), exécutables avec `python tests/...`. Ils sont **alignés sur l’architecture `app.*` uniquement** (plus d’imports `services/`, `core/` ou `schemas/` legacy). Voir `ARCHITECTURE_VALIDATION_REPORT.md` pour le détail de la migration.

---

## 2. Configuration et fixtures partagées (`conftest.py`)

Le fichier **`tests/conftest.py`** est chargé par pytest et fournit :

### 2.1 Markers

Déclarés dans **`pytest.ini`** (`e2e`, `integration`, `unit`, `asyncio`, …) pour éviter les avertissements et filtrer (`pytest -m "not e2e"`, `-m unit`, etc.).

- **`e2e`** : smoke / bout-en-bout (ex. `pytest -m "not e2e"` pour la CI).
- **`unit`** / **`integration`** : catégories utilisées dans les modules de tests.

### 2.2 Client HTTP

- **`client`** : `TestClient(app)` sur `app.main.app` pour tous les tests API.
- **`async_client`** : tuple `(transport, app)` pour `httpx.AsyncClient` (optionnel, nécessite `httpx` et `pytest-asyncio`).

### 2.3 Authentification

- **`auth_headers`** : en-têtes `Authorization: Bearer <token>`.
  - Appel à `POST /api/auth/login` avec `TEST_USER_EMAIL` et `TEST_USER_PASSWORD` (variables d’environnement).
  - Si variables absentes ou login en échec → `{}` ; les tests gèrent alors 401 ou skip.

### 2.4 Base de données

- **`supabase_client`** : client Supabase (projet de test si `SUPABASE_TEST_URL` et `SUPABASE_TEST_KEY`, sinon config par défaut). Peut être `None`.
- **`db_session`** : alias de `supabase_client` pour les tests repository / intégration.

### 2.5 Données de test

- **`test_user_id`** : depuis `TEST_USER_ID` ou dérivé du login.
- **`test_company_id`** : depuis `TEST_COMPANY_ID` ou première company en DB de test.
- **`test_employee_id`** : depuis `TEST_EMPLOYEE_ID` ou premier employé de `test_company_id`.

Les tests qui dépendent de la DB réelle peuvent **skip** si ces fixtures sont `None`.

---

## 3. Fonctionnement par type de test

### 3.1 Tests unitaires (`unit/`)

- **Pas d’appel HTTP ni de DB** : on mocke les dépendances (`get_supabase_client`, repositories, providers).
- **Fichiers typiques** :
  - `test_domain.py` : règles pures, constantes, value objects (ex. `auth.domain.rules`, `employees.domain.rules`).
  - `test_service.py` : services applicatifs avec repositories mockés.
  - `test_commands.py` / `test_queries.py` : commandes et queries avec `@patch` sur le module cible (ex. `_employee_repository`, `get_storage_provider`).
- **Convention** : `pytestmark = pytest.mark.unit` en tête de module.

Exemple (queries) :

```python
@patch("app.modules.employees.application.queries._employee_repository")
def test_get_employees_returns_enriched_list(mock_repo):
    mock_repo.get_by_company.return_value = [...]
    result = queries_module.get_employees("company-1")
    mock_repo.get_by_company.assert_called_once_with("company-1")
    assert len(result) == 1
```

### 3.2 Tests d’intégration API (`integration/<module>/test_api.py`)

- **Client** : fixture `client` (TestClient).
- **Auth** : soit `auth_headers` (JWT réel si env configurée), soit **`dependency_overrides`** pour injecter un utilisateur de test sans JWT.
- **DB / services** : souvent **patch** des services ou repositories pour éviter DB et appels externes ; les tests vérifient status HTTP, forme des réponses et appels aux mocks.

Pattern typique avec utilisateur RH injecté :

```python
from app.main import app
from app.core.security import get_current_user

@pytest.fixture
def client_with_rh(self, client, mock_repo):
    app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
    with patch("app.modules.<module>.application.service.get_repository", return_value=mock_repo):
        yield client
    app.dependency_overrides.pop(get_current_user, None)
```

- **Convention** : `pytestmark = pytest.mark.integration` ; classes `Test*` par route ou groupe de routes (ex. `TestGetEmployees`, `TestAnnualReviewsWithRhUser`).

### 3.3 Tests d’intégration repository (`integration/<module>/test_repository.py`)

- **Supabase mocké** : `@patch("app.modules.<module>.infrastructure.repository.supabase")` (ou équivalent) pour contrôler les réponses.
- **DB réelle** : avec `db_session` / `supabase_client` et variables d’env de test ; les tests peuvent skip si client non disponible.

### 3.4 Tests d’intégration wiring (`integration/<module>/test_wiring.py`)

- Vérifient que le **câblage** du module est correct : interfaces repository, usage des règles domaine par les mappers, flux application → repository.
- Peuvent combiner instanciation réelle des repositories et patch des dépendances pour isoler un flux.

### 3.5 Tests E2E (`e2e/`)

- **test_smoke_global.py** : app démarre, `GET /health`, `GET /openapi.json`, login/me basiques.
- **test_smoke_modules.py** : un appel HTTP minimal par module exposé (ex. `GET /api/employees`, `GET /api/annual-reviews`) ; on accepte 200, 401, 403, 404, 422, mais **pas 500**.
- **test_auth_flow.py** : login (200 + token ou 401), `GET /api/auth/me` sans auth (401), avec token (200 si configuré).
- **cross_module/test_cross_flows.py** : enchaînement d’appels (login → my-companies, etc.) avec `client` et `auth_headers`.

Convention : **`pytestmark = pytest.mark.e2e`** en tête de module.

---

## 4. Conventions de code

### 4.1 Nommage

- **Fichiers** : `test_<sujet>.py` (ex. `test_domain.py`, `test_api.py`, `test_repository.py`, `test_wiring.py`).
- **Classes** : `Test*` pour grouper les cas (ex. `TestGetEmployees`, `TestAnnualReviewsUnauthenticated`).
- **Fonctions** : `test_<comportement>_<résultat>` ou `test_<route>_<scénario>` (ex. `test_get_employees_without_auth_returns_401`, `test_me_with_valid_token`).

### 4.2 Structure d’un test

- **Docstring** : une phrase courte décrivant le scénario et le résultat attendu (ex. « Sans token → 401 », « GET /api/annual-reviews en tant que RH → 200 et liste »).
- **Arrange / Act / Assert** : données et mocks, appel (route ou fonction), assertions sur status, body ou appels mockés.

### 4.3 Assertions

- **API** : `assert response.status_code == ...` ; pour le body : `response.json()` et assertions sur les champs utiles.
- **Unit** : `assert` sur la valeur de retour et `mock.assert_called_once_with(...)` (ou équivalent) pour les interactions.
- **E2E smoke** : accepter plusieurs status possibles (ex. 200/401/403/404/422) selon auth et données, mais **toujours refuser 500**.

### 4.4 Gestion de l’auth et des données manquantes

- Si `auth_headers` est vide (pas de token) : tester 401 ou `pytest.skip("auth_headers non configuré")` selon le but du test.
- Si une fixture DB (`supabase_client`, `db_session`, `test_company_id`, …) est `None` : **skip** ou accepter un comportement dégradé (ex. 403/404) sans faire échouer pour « env non configurée ».

### 4.5 Nettoyage

- Après usage de **`app.dependency_overrides`** : toujours faire `app.dependency_overrides.pop(get_current_user, None)` (dans un `try/finally` ou fixture avec `yield`).
- Les **patch** sont en général limités au scope du test ou de la fixture (contexte `with` ou décorateur sur la fonction).

### 4.6 Imports et dépendances

- **Unit** : importer le module ou la classe testée (ex. `from app.modules.employees.application import queries as queries_module`) et patcher au chemin où il est **utilisé** (ex. `app.modules.employees.application.queries._employee_repository`).
- **Integration** : `from app.main import app` pour `dependency_overrides` ; `from fastapi.testclient import TestClient` ; schémas (ex. `User`, `CompanyAccess`) pour construire l’utilisateur injecté.

---

## 5. Exécution des tests

Depuis la racine **`backend_api`** :

```bash
# Tous les tests
pytest tests/

# Exclure les E2E (utile en CI sans env auth/DB)
pytest tests/ -m "not e2e"

# Un répertoire
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# Un module
pytest tests/unit/employees/
pytest tests/integration/annual_reviews/

# Un fichier ou une fonction
pytest tests/unit/auth/test_domain.py
pytest tests/unit/auth/test_domain.py::TestIsEmailLike::test_contains_at_returns_true
```

Variables d’environnement utiles :

- **Auth** : `TEST_USER_EMAIL`, `TEST_USER_PASSWORD` (pour `auth_headers` et tests E2E avec token).
- **DB de test** : `SUPABASE_TEST_URL`, `SUPABASE_TEST_KEY` (optionnel).
- **IDs de test** : `TEST_USER_ID`, `TEST_COMPANY_ID`, `TEST_EMPLOYEE_ID` (optionnel, pour tests intégration/E2E ciblés).

---

## 6. Fixtures et données supplémentaires

- **`tests/fixtures/`** : fixtures partagées (réutilisables par plusieurs modules).
- **`tests/migration/fixtures.py`** : construction de jeux de données pour comparaison payroll (contrats, cumuls, calendriers, etc.) — utilisé par les tests de migration / régression paie. Les chemins disque suivent **`app.core.paths`** (runtime sous **`app/runtime/payroll/`**).
- **`tests/unit/core/test_paths_payroll_runtime.py`** : contrôle que la racine paie n’est pas `backend_calculs/` et que les templates bulletin sont présents.

Les commentaires dans **`conftest.py`** décrivent, par module, les fixtures optionnelles (ex. `employees_headers`, `annual_reviews_headers`, `*_db_session`) et le format des en-têtes pour des tests E2E avec token réel.

---

## 7. Résumé des conventions

| Élément | Convention |
|--------|-------------|
| Fichiers | `test_<sujet>.py` dans `unit/<module>/` ou `integration/<module>/` ou `e2e/` |
| Markers | `pytestmark = pytest.mark.unit` / `integration` / `e2e` en tête de module |
| API | `client`, `auth_headers` ou `dependency_overrides` + patch services/repos |
| Unit | Mocker repositories/providers ; pas de DB ni HTTP |
| E2E | Accepter 200/401/403/404/422, jamais 500 pour les smoke |
| Nettoyage | Toujours retirer les `dependency_overrides` après le test |
| Skip | Si `auth_headers` ou DB non configurés et nécessaire au scénario |

Ce README et le `conftest.py` servent de référence pour garder une architecture et des conventions de tests cohérentes dans le backend API.
