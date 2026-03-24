# Analyse d'autonomie — module saisies_avances

## Étape A — Imports legacy identifiés

### 1. `core.config` (supabase)

| Fichier | Symbole | Usage | Cible |
|---------|---------|--------|-------|
| `infrastructure/repository.py` | `supabase` | Accès DB (tables salary_seizures, salary_advances, salary_advance_payments, employees) | `app.core.database` |
| `infrastructure/queries.py` | `supabase` | Requêtes complexes (listes, jointures, période) | `app.core.database` |
| `infrastructure/providers.py` | `supabase` | Storage bucket advance_payments (signed URLs, remove) | `app.core.database` |

**Type :** Accès DB / client Supabase. **Cible :** `app.core.database` (déjà centralisé dans la nouvelle archi).

---

### 2. `security` (User, get_current_user)

| Fichier | Symbole | Usage | Cible |
|---------|---------|--------|-------|
| `api/router.py` | `User`, `get_current_user` | Dépendance FastAPI pour l’auth sur les routes protégées | `app.core.security` (get_current_user), `app.modules.users.schemas.responses` (User) |

**Type :** Sécurité transverse. **Cible :** `app.core.security` pour `get_current_user`, `app.modules.users.schemas.responses.User` pour le type (ou réexport depuis app.core si présent).

---

### 3. `services.saisies_avances_integration` (enrich_payslip_with_seizures_and_advances)

| Fichier | Symbole | Usage | Cible |
|---------|---------|--------|-------|
| `application/service.py` | `enrich_payslip_with_seizures_and_advances` | Enrichissement bulletin (saisies + avances, écriture historique) | Logique réimplémentée dans le module : domain.rules + infrastructure.queries + nouveau infrastructure/enrichment.py (écritures) |

**Type :** Service legacy. **Cible :** Réimplémentation dans le module avec :
- `domain.rules` : `calculate_seizable_amount`, `apply_priority_order`, `calculate_seizure_deduction`
- `infrastructure.queries` : `get_seizures_for_period`, `get_advances_to_repay`
- Nouveau `infrastructure/enrichment.py` : écritures `salary_seizure_deductions`, `salary_advance_repayments`, mise à jour `salary_advances` via `app.core.database.supabase`

---

## Dépendances à conserver temporairement (wrappers)

Aucune. Après migration :
- Supabase : `app.core.database` (déjà dans app/*).
- Auth : `app.core.security` + User dans app.modules.users.
- Enrichissement : entièrement dans le module, plus d’appel à `services.*`.

---

## Récapitulatif des changements

1. Remplacer `from core.config import supabase` par `from app.core.database import supabase` dans repository, queries, providers.
2. Remplacer `from security import User, get_current_user` par imports depuis `app.core.security` et `app.modules.users.schemas.responses` dans le router.
3. Créer `infrastructure/enrichment.py` (lectures existence déduction/remboursement + écritures) avec `app.core.database.supabase`.
4. Implémenter `enrich_payslip` dans `application/service.py` en s’appuyant sur domain, queries et enrichment, sans aucun import `services.*`.

---

## Étape C — Vérification d'autonomie (après migration)

- Aucun fichier dans `app/modules/saisies_avances` n'importe : `api/*`, `schemas/*` (legacy), `services/*`, `core.*` (legacy), ni aucun chemin hors `app/*`.
- Imports restants : `app.core.database`, `app.core.security`, `app.modules.saisies_avances.*`, `app.modules.users.schemas.responses` (User), plus stdlib et libs externes (fastapi, pydantic).
- Comportement HTTP et métier inchangé (endpoints, méthodes, paramètres, réponses, logique d'enrichissement bulletin identique).

**Verdict final : module autonome.** Aucun wrapper temporaire conservé.
