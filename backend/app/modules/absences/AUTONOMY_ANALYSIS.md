# Analyse des dépendances legacy — module absences (autonomie)

## Étape A — Imports legacy restants

### 1. Fichier : `app/modules/absences/infrastructure/providers.py`

| Ligne | Import legacy | Symbole(s) | Usage | Type |
|-------|----------------|------------|--------|------|
| 25 | `from services.evenements_familiaux import` | `get_events_disponibles`, `get_solde_evenement` | `EvenementFamilialQuotaProvider.get_events_disponibles` et `get_solde_evenement` (quota / solde événements familiaux selon CC) | Service legacy |
| 26 | `from services.salary_certificate_generator import` | `SalaryCertificateGenerator` | `SalaryCertificateProvider.generate_for_absence` : génération PDF attestation salaire + rémunération de référence | Service legacy |

### 2. Autres fichiers du module

- **api/router.py** : `app.core.security`, `app.modules.users.schemas.responses` → déjà sous `app/*`, pas legacy.
- **infrastructure/queries.py**, **infrastructure/repository.py** : `app.core.database` → déjà sous `app/*`, pas legacy.
- Aucun import vers `api/*`, `schemas/*`, `core/*` (racine), `backend_calculs/*`.

---

## Cible par dépendance

| Dépendance | Cible dans la nouvelle architecture | Action |
|------------|--------------------------------------|--------|
| `services.evenements_familiaux` | `app/modules/absences/infrastructure/evenements_familiaux.py` | Recopier la logique (tables employees, company_collective_agreements, cc_evenements_familiaux, evenements_familiaux_reference, absence_requests) et utiliser `app.core.database.supabase`. Logique purement absences / conventions collectives, pas partagée. |
| `services.salary_certificate_generator` | `app/modules/absences/infrastructure/salary_certificate_generator.py` | Recopier la classe, utiliser `app.core.database.supabase` et des helpers PDF sous `app/*`. |
| Dépendance transitive : `services.solde_common.pdf_helpers` | `app/shared/infrastructure/pdf/helpers.py` | Créer module partagé avec `setup_custom_styles`, `format_date`, `format_currency`, `safe_float`, `safe_str` (utilisés par le générateur d’attestation). Utilitaires génériques PDF/formatage. |

---

## Wrappers temporaires conservés

Aucun. Les deux services sont intégrés dans le module (copie de la logique dans `app/modules/absences/infrastructure/` et usage de `app.core.database`). Aucun wrapper vers `services/*` conservé dans le module absences.

---

## Résumé

- **Imports legacy à supprimer** : 2 (tous deux dans `infrastructure/providers.py`).
- **Nouveaux fichiers à créer** :
  1. `app/shared/infrastructure/pdf/helpers.py` — helpers PDF génériques (sans dépendance legacy).
  2. `app/modules/absences/infrastructure/evenements_familiaux.py` — logique événements familiaux, DB via `app.core.database`.
  3. `app/modules/absences/infrastructure/salary_certificate_generator.py` — génération attestation salaire, DB via `app.core.database`, PDF via `app.shared.infrastructure.pdf.helpers`.
- **Fichier à modifier** : `app/modules/absences/infrastructure/providers.py` — remplacer les imports `services.*` par les nouveaux modules sous `app/*`.

---

## Étape C — Vérification d'autonomie

### 1. Aucun import legacy restant

Vérification : `grep 'from (api\.|schemas\.|services\.|core\.|security|backend_calculs)' app/modules/absences/**/*.py` → **aucun résultat**.

- Aucun fichier dans `app/modules/absences` n'importe `api/*`, `schemas/*`, `services/*`, `core/*` (racine), `backend_calculs/*`.

### 2. Imports restants uniquement sous app/* et librairies

- `app.core.database` (supabase) — infrastructure partagée.
- `app.core.security` (get_current_user) — sécurité partagée.
- `app.modules.users.schemas.responses` (User) — contrat inter-module (auth).
- `app.shared.infrastructure.pdf.helpers` — helpers PDF génériques.
- `app.modules.absences.*` — interne au module.
- Librairies : fastapi, pydantic, reportlab, stdlib.

### 3. Comportement HTTP et métier

- Aucun changement d’endpoints, méthodes HTTP, préfixes, paramètres, body, response models, codes de statut.
- Logique événements familiaux et génération d’attestation salaire recopiée à l’identique ; seules les sources d’import (DB via `app.core.database`, PDF via `app.shared.infrastructure.pdf.helpers`) ont été basculées.

---

## Imports legacy supprimés

| Fichier | Import supprimé |
|---------|-----------------|
| `infrastructure/providers.py` | `from services.evenements_familiaux import get_events_disponibles, get_solde_evenement` |
| `infrastructure/providers.py` | `from services.salary_certificate_generator import SalaryCertificateGenerator` |

---

## Nouveaux fichiers créés ou complétés dans app/*

| Fichier | Description |
|---------|-------------|
| `app/shared/infrastructure/pdf/helpers.py` | Nouveau. Helpers PDF : `setup_custom_styles`, `format_date`, `format_currency`, `safe_float`, `safe_str`. Aucune dépendance legacy. |
| `app/modules/absences/infrastructure/evenements_familiaux.py` | Nouveau. Logique quota/solde événements familiaux (ex. services/evenements_familiaux), utilise `app.core.database`. |
| `app/modules/absences/infrastructure/salary_certificate_generator.py` | Nouveau. Classe `SalaryCertificateGenerator` (ex. services/salary_certificate_generator), utilise `app.core.database` et `app.shared.infrastructure.pdf.helpers`. |
| `app/modules/absences/infrastructure/providers.py` | Modifié. Imports `services.*` remplacés par les modules ci-dessus. |

---

## Wrappers temporaires conservés

**Aucun.** Aucun wrapper vers le legacy conservé dans le module absences.

---

## Verdict final

**Module autonome.** Le module `app/modules/absences` ne dépend plus d’aucun élément legacy hors `app/*`. Il peut fonctionner dans la nouvelle architecture en s’appuyant uniquement sur `app.core`, `app.shared` et `app.modules` (dont `app.modules.users` pour le schéma `User`). Comportement fonctionnel et contrat HTTP inchangés.
