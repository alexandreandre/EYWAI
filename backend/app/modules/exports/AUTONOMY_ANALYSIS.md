# Module exports — Autonomie structurelle

## Verdict final

**Module autonome** — `app/modules/exports` ne dépend plus d’aucun élément legacy hors `app/*`.

---

## Étape A — Imports legacy identifiés (avant migration)

| Fichier | Import legacy | Symbole | Usage | Cible |
|---------|----------------|---------|--------|-------|
| `infrastructure/repository.py` | `core.config` | `supabase` | Accès DB Supabase | `app.core.database` |
| `infrastructure/storage.py` | `core.config` | `supabase` | Upload / signed URL | `app.core.database` |
| `infrastructure/queries.py` | `core.config` | `supabase` | Requêtes exports_history, profiles | `app.core.database` |
| `infrastructure/providers.py` | `services.exports` | journal_paie, paiement_salaires, ecritures_comptables, formats_cabinet, dsn | Génération des exports | Implémentations locales dans `infrastructure/export_*.py` |

Les implémentations `services/exports/*` dépendaient elles-mêmes de :
- `core.config.supabase` → `app.core.database.supabase`
- `services.export_service` (generate_csv, generate_xlsx, format_currency, format_period) → `app.shared.utils.export`

---

## Étape B — Modifications effectuées

### 1. Remplacement `core.config` → `app.core.database`

- **repository.py** : `from core.config import supabase` → `from app.core.database import supabase`
- **storage.py** : idem
- **queries.py** : idem

### 2. Utilitaires partagés dans `app/shared/utils/export.py`

- **generate_csv** : génération CSV UTF-8 BOM (aligné sur `services/export_service.py`)
- **format_currency** : montant en devise française
- **format_period** : période YYYY-MM → libellé (ex. Janvier 2024)

`generate_xlsx` existait déjà dans ce fichier.

### 3. Implémentations locales dans `app/modules/exports/infrastructure/`

| Fichier | Rôle | Remplace |
|---------|------|----------|
| `export_journal_paie.py` | Journal de paie (preview, génération CSV/XLSX) | `services/exports/journal_paie.py` |
| `export_paiement_salaires.py` | Paiement salaires / virements (preview, export, fichier bancaire) | `services/exports/paiement_salaires.py` |
| `export_ecritures_comptables.py` | OD salaires, charges sociales, PAS (preview, génération) | `services/exports/ecritures_comptables.py` |
| `export_formats_cabinet.py` | Formats cabinet (générique, Quadra, Sage) | `services/exports/formats_cabinet.py` |
| `export_dsn.py` | DSN (preview, génération XML) | `services/exports/dsn.py` |

Tous importent uniquement :
- `app.core.database` (supabase)
- `app.shared.utils.export` (generate_csv, generate_xlsx, format_currency, format_period)
- Entre eux : `export_formats_cabinet` utilise `export_ecritures_comptables` (import relatif `.export_ecritures_comptables`).

### 4. Mise à jour de `providers.py`

- Suppression des imports dynamiques vers `services.exports.*`.
- Délégation directe vers les modules locaux `export_journal_paie`, `export_paiement_salaires`, `export_ecritures_comptables`, `export_formats_cabinet`, `export_dsn`.
- Signatures et noms de fonctions inchangés pour l’application.

---

## Étape C — Vérification autonomie

### Imports restants dans `app/modules/exports`

- **app.core** : `security` (get_current_user), `database` (supabase)
- **app.modules** : `exports` (interne), `users.schemas.responses` (User pour le router)
- **app.shared** : `utils.export` (generate_csv, generate_xlsx, format_currency, format_period)
- **Bibliothèques** : fastapi, pydantic, typing, datetime, etc.

Aucun import vers : `api/*`, `schemas/*` (legacy), `services/*`, `core` (sans préfixe `app.`), `backend_calculs/*`.

### Wrappers temporaires conservés

Aucun. Le module ne s’appuie plus sur des wrappers de compatibilité legacy.

### Comportement

- Endpoints, méthodes HTTP, préfixes, paramètres, body/response models et codes de statut inchangés.
- Logique métier reproduite dans les `export_*.py` à partir des services legacy (copie adaptée des imports uniquement).
- Amélioration mineure : `preview_od` gère désormais `od_globale` comme `od_salaires` (alignement avec le flux de génération).

---

## Fichiers créés ou modifiés (résumé)

| Fichier | Action |
|---------|--------|
| `app/modules/exports/infrastructure/repository.py` | Modifié (import supabase) |
| `app/modules/exports/infrastructure/storage.py` | Modifié (import supabase) |
| `app/modules/exports/infrastructure/queries.py` | Modifié (import supabase) |
| `app/modules/exports/infrastructure/providers.py` | Remplacé (délégation vers export_*.py) |
| `app/modules/exports/infrastructure/export_journal_paie.py` | Créé |
| `app/modules/exports/infrastructure/export_paiement_salaires.py` | Créé |
| `app/modules/exports/infrastructure/export_ecritures_comptables.py` | Créé |
| `app/modules/exports/infrastructure/export_formats_cabinet.py` | Créé |
| `app/modules/exports/infrastructure/export_dsn.py` | Créé |
| `app/shared/utils/export.py` | Complété (generate_csv, format_currency, format_period) |

Aucun fichier legacy (`api/*`, `schemas/*`, `services/*`, `core/*` racine) n’a été supprimé ; ils restent utilisables par le reste de l’application.
