# Analyse des dépendances legacy — module medical_follow_up

## Imports legacy identifiés

| Fichier | Import legacy | Symbole | Usage | Cible |
|---------|----------------|---------|--------|-------|
| application/service.py | services.medical_follow_up_service | compute_obligations_for_employee | Moteur de règles (calcul + upsert obligations VIP, SIR, reprise, etc.) | infrastructure/obligation_engine.py (nouveau) |
| infrastructure/providers.py | services.medical_follow_up_service | get_company_medical_setting | Lecture « module activé » (legacy = True) | Provider lit table companies.settings.medical_follow_up_enabled (défaut True) |
| infrastructure/database.py | core.config | supabase | Fallback si app.core.database absent | Supprimer fallback ; n’utiliser que app.core.database |

## Dépendances déjà dans app/* (conservées)

- app.core.security.get_current_user
- app.core.database (utilisé après suppression du fallback)
- app.modules.users.schemas.responses.User

## Actions

1. **database.py** : ne plus importer core.config ; lever une erreur si app.core.database indisponible.
2. **providers.py** : implémenter is_enabled par query Supabase sur companies.settings (medical_follow_up_enabled, défaut True).
3. **obligation_engine.py** (nouveau) : recopie du moteur legacy avec client Supabase fourni par infrastructure.database.
4. **service.py** : appeler obligation_engine.compute_obligations_for_employee au lieu du service legacy.

## Wrappers temporaires conservés

Aucun.

## Étape C — Vérification d’autonomie

- Aucun fichier dans app/modules/medical_follow_up n’importe : api/*, services/*, core.config, schemas/* (racine).
- Imports restants : app.core (security, database), app.modules.users (User), app.modules.medical_follow_up (interne), stdlib, fastapi, pydantic.
- Comportement HTTP et métier inchangé (même moteur, même lecture settings, même client DB via app.core.database).

## Verdict

**Module autonome** (sans wrappers temporaires).
