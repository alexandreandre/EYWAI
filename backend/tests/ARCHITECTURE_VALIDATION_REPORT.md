# Rapport d’audit & validation — tests alignés sur `app/`

**Dernière mise à jour** : 2026-03-23 — alignement tests migration paie + `tests/unit/core/test_paths_payroll_runtime.py` (runtime sous `app/runtime/payroll/`, plus de chemin actif vers `backend_calculs/` pour l’API).

---

## Étape 1 — Audit complet

### Recherches effectuées (fichiers `tests/**/*.py`)

| Pattern cible | Résultat |
|---------------|----------|
| `from services.` | **0** |
| `from core.` (hors `app.core`) | **0** |
| `from schemas.` (racine legacy) | **0** |
| `from api.routers` (hors `app.`) | **0** |
| `from main import app` (ancien point d’entrée) | **0** (corrigé → `from app.main import app`) |
| `backend_calculs` (import Python dans `tests/`) | **0** (audit migré ; runtime paie testé via `app.core.paths`) |

### Imports hors `app.*` détectés par analyse AST (hors stdlib / pytest / FastAPI / etc.)

- **`from tests.migration.fixtures`** — `tests/migration/test_payroll_bulletin_compare_forfait.py`, `test_payroll_bulletin_compare_heures.py`  
  - **Statut** : **acceptable** — fixtures partagées du **paquet de tests** `tests`, pas du code applicatif legacy.

---

## Étape 2 — Migrations réalisées (session 2026-03-23)

| Fichier | Modification |
|---------|----------------|
| `test_bonus_types.py` | `from main import app` → `from app.main import app` |
| `migration/test_payroll_transfer_audit.py` | Suppression de la dépendance à `backend_calculs.moteur_paie` ; test `test_engine_contexte_exports_contexte_paie` sur `app.modules.payroll.engine.contexte` uniquement ; docstring alignée sur `app/` |
| `migration/__init__.py` | Commentaire sans référence obligatoire à `backend_calculs` |
| `conftest.py` | `collect_ignore` pour `test_login.py` et `test_absenteeism.py` (scripts manuels avec code au niveau module — évite erreurs de collecte pytest) |

**Imports legacy supprimés / remplacés (cette session)** : **2** (`main`, `backend_calculs`).

### Mise à jour 2026-03-23 (runtime paie)

| Fichier | Modification |
|---------|----------------|
| `tests/unit/core/test_paths_payroll_runtime.py` | **Nouveau** : racine paie sous `app/`, absence de `backend_calculs` dans le chemin, présence des templates bulletin |
| `tests/migration/test_payroll_bulletin_compare_heures.py` / `..._forfait.py` | `payroll_engine_employee_folder()` au lieu de concaténation `data/employes/` |
| `tests/migration/README.md`, `fixtures.py` (docstring) | Documentation chemins → `app/runtime/payroll/` |
| `tests/README.md` | Section `unit/core/` + lien vers test des paths |
| `tests/migration/PAYROLL_TRANSFER_AUDIT.md` | Encadré runtime disque |
| `tests/test_forfait_jour_complet.py` | Commentaire d’en-tête simplifié |

---

## Étape 3 — Nettoyage & structure

- Les scripts racine `test_*.py` (smoke manuels, souvent Supabase réel) restent en place ; ils utilisent déjà `app.*` pour le code métier.
- Pas de suppression massive de tests : l’audit n’a pas révélé de fichiers entièrement basés sur `services/` ou `schemas/` racine.
- Arborescence existante conservée : `unit/`, `integration/`, `e2e/`, `migration/`, scripts racine.

---

## Étape 4 — Validation finale

### Imports interdits (policy)

| Pattern | Statut |
|---------|--------|
| `from services.` | **0** |
| `from core.` (legacy, hors `app.core`) | **0** |
| `from schemas.` (legacy racine) | **0** |

### Cas explicitement acceptables

| Cas | Justification |
|-----|----------------|
| `from app.core.*` | Couche transverse (config, DB, sécurité) — prévue par l’architecture. |
| `from app.modules.*.schemas` | Schémas Pydantic du module — prévu. |
| `from tests.*` | Utilitaires **internes au dossier de tests** uniquement. |
| `supabase`, `httpx`, `pytest`, `fastapi`, etc. | Bibliothèques externes. |

### Zones non bloquantes (évolution possible)

- **Accès Supabase** via `app.core.database` dans certains scripts racine (`test_absenteeism.py`, `test_upload.py`, etc.) : utile pour smoke manuel ; pour une politique stricte « zéro DB hors API », il faudrait les réécrire en `TestClient` + mocks (chantier séparé).
- **`sys.path.insert`** encore présents dans quelques `test_*_complet.py` / `test_password_reset.py` : permettent l’exécution en script ; pourrait être unifié via `PYTHONPATH=.` ou packaging.

---

## Synthèse chiffrée (état actuel)

- **Fichiers modifiés dans cette passe** : **5** (`test_bonus_types.py`, `migration/test_payroll_transfer_audit.py`, `migration/__init__.py`, `conftest.py`, ce rapport).
- **Imports problématiques traités** : **2** (voir tableau ci-dessus).
- **Fichiers Python sous `tests/`** : **~150+** (hors `__pycache__`) — l’ensemble est aligné sur `app.*` pour le code applicatif.

### Commandes utiles

```bash
cd backend_api
./venv/bin/pytest tests/unit tests/integration tests/e2e -q --collect-only
./venv/bin/pytest tests/migration/test_payroll_transfer_audit.py -q
```

---

*Rapport mis à jour après audit AST + greps ciblés sur `backend_api/tests`.*
