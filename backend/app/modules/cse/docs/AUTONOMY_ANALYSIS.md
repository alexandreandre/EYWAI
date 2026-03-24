# Analyse des dépendances legacy — module CSE

## 1. Imports legacy identifiés

| Fichier | Import legacy | Symbole(s) | Usage | Cible app/* |
|---------|----------------|------------|--------|-------------|
| api/router.py | security | User, get_current_user | Auth sur toutes les routes | app.core.security.get_current_user, app.modules.users.schemas.responses.User |
| application/queries.py | services.cse_service | _check_module_active | No-op module actif | Inline no-op dans queries.py |
| application/commands.py | services.cse_service | create_*, update_*, add_*, remove_*, start_*, stop_*, upload_*, process_* | Toutes les écritures | app.modules.cse.infrastructure.cse_service_impl |
| application/commands.py | services.cse_ai_service | process_recording | Traitement IA enregistrement | app.modules.cse.infrastructure.cse_ai_impl |
| infrastructure/queries.py | core.config | supabase | Requêtes Supabase (quotas, minutes) | app.core.database.supabase |
| infrastructure/repository.py | services.cse_service | get_*, _is_elected_member | Toutes les lectures + élu actif | app.modules.cse.infrastructure.cse_service_impl |
| infrastructure/providers.py | services.cse_pdf_service | generate_convocation_pdf, generate_minutes_pdf, generate_election_calendar_pdf | Génération PDF | app.modules.cse.infrastructure.cse_pdf_impl |
| infrastructure/providers.py | services.cse_export_service | export_elected_members, export_delegation_hours, export_meetings_history | Exports Excel | app.modules.cse.infrastructure.cse_export_impl |
| infrastructure/providers.py | services.cse_ai_service | process_recording | IA enregistrement | app.modules.cse.infrastructure.cse_ai_impl |

## 2. Cibles dans la nouvelle architecture

- **Sécurité** : app.core.security (existant), app.modules.users.schemas.responses.User (existant).
- **DB** : app.core.database.supabase (existant).
- **Logique CSE (lectures/écritures)** : app.modules.cse.infrastructure.cse_service_impl (nouveau, copie de services/cse_service.py avec imports app/*).
- **PDF CSE** : app.modules.cse.infrastructure.cse_pdf_impl (nouveau, copie de services/cse_pdf_service.py).
- **Export Excel** : app.modules.cse.infrastructure.cse_export_impl (nouveau) + app.shared.utils.export.generate_xlsx (nouveau, partagé).
- **IA enregistrement** : app.modules.cse.infrastructure.cse_ai_impl (nouveau, copie de services/cse_ai_service.py).
- **check_module_active** : no-op inline dans application/queries.py (comportement identique au legacy).

## 3. Wrappers temporaires conservés

Aucun. Après migration, le module n’a plus de dépendance vers api/*, schemas/*, services/*, core/* legacy.

## 4. Fichiers créés/complétés

- **app/shared/utils/export.py** : `generate_xlsx` (réutilisable par d’autres modules).
- **app/modules/cse/infrastructure/cse_service_impl.py** : logique complète ex-services/cse_service.py (supabase + schémas depuis app.*).
- **app/modules/cse/infrastructure/cse_pdf_impl.py** : logique ex-services/cse_pdf_service.py (sans import legacy).
- **app/modules/cse/infrastructure/cse_export_impl.py** : logique ex-services/cse_export_service.py (utilise app.shared.utils.export).
- **app/modules/cse/infrastructure/cse_ai_impl.py** : logique ex-services/cse_ai_service.py (supabase depuis app.core.database).

## 5. Vérification d’autonomie

- Aucun fichier dans app/modules/cse n’importe : api/*, schemas/*, services/*, core/* (legacy).
- Imports restants : app.core.*, app.modules.*, app.shared.*, bibliothèques externes (fastapi, pydantic, reportlab, openpyxl, etc.).

## 6. Verdict final

**Module autonome.** Aucun wrapper temporaire conservé ; le module ne dépend plus d’aucun élément legacy hors app/*.
