# Sources de vérité — copilot RH

Lire ces fichiers **dans l'ordre** lors d'une actualisation.

## 1. Navigation & parcours utilisateur

| Fichier | Contenu |
|---------|---------|
| `frontend/src/components/ui/app-sidebar.tsx` | Menu RH complet (Team, Gestion, Paie), badges workflow |
| `frontend/src/components/ui/employee-sidebar.tsx` | Menu collaborateur |
| `frontend/src/pages/rh/Dashboard.tsx` | Widgets tableau de bord, bouton « Demander à l'IA » |
| `frontend/src/components/CopilotModalAgent.tsx` | Description affichée à l'utilisateur (périmètre annoncé) |

## 2. Fiches métier (onglets collaborateur)

| Fichier | Contenu |
|---------|---------|
| `frontend/src/features/employee-detail/` | Onglets fiche salarié |
| `frontend/src/features/payroll/` | Parcours paie, bulletins |
| `frontend/src/features/recruitment/` | Pipeline recrutement |
| `frontend/src/pages/rh/` | Pages RH par module |

## 3. Backend copilot (cibles de mise à jour)

| Fichier | Rôle |
|---------|------|
| `backend/app/modules/copilot/infrastructure/app_knowledge.py` | `APP_FEATURE_GUIDE` |
| `backend/app/modules/copilot/domain/tools.py` | Catalogue fermé `ToolName` + parsing args |
| `backend/app/modules/copilot/infrastructure/secure_queries.py` | Requêtes scopées `company_id` serveur |
| `backend/app/modules/copilot/application/tool_service.py` | Dispatch outil → handler |
| `backend/app/modules/copilot/infrastructure/providers.py` | Prompts LLM, few-shots intent |
| `backend/app/modules/copilot/application/commands.py` | Orchestration intent → réponse |
| `backend/tests/unit/copilot/test_app_knowledge.py` | Tests guide produit |
| `backend/tests/unit/copilot/test_tools.py` | Tests catalogue fermé |
| `backend/tests/unit/copilot/test_secure_queries.py` | Tests scoping requêtes |

**Ne pas recréer** `schema_context.py` / text-to-SQL (supprimés volontairement).

## 4. Schéma Supabase (référence pour nouveaux outils)

| Source | Usage |
|--------|-------|
| `supabase/migrations/*.sql` | CREATE TABLE, ALTER, enums, contraintes |
| `backend/app/modules/*/infrastructure/repository.py` | Colonnes réellement lues/écrites |
| `backend/app/modules/*/infrastructure/queries.py` | Jointures et filtres company_id |
| [schema-tables-rh.md](schema-tables-rh.md) | Inventaire tables RH pour outils futurs |

Commandes utiles :

```bash
# Tables créées
rg "CREATE TABLE" supabase/migrations/ --no-heading

# Colonnes récemment ajoutées
rg "ADD COLUMN" supabase/migrations/ --no-heading | tail -50

# Tables déjà utilisées par le catalogue Copilot
rg '\.table\("' backend/app/modules/copilot/infrastructure/secure_queries.py
```

## 5. Conventions collectives

| Fichier | Contenu |
|---------|---------|
| `backend/app/modules/copilot/infrastructure/queries.py` | `get_company_collective_agreements` |
| Tables `collective_agreements_catalog`, `company_collective_agreements`, `collective_agreement_texts` | Déjà branchées — pas de doc supplémentaire sauf nouvelle table CC |

## 6. Hors périmètre (ne pas documenter dans le copilot RH)

- `scraping_*` — veille réglementaire admin plateforme
- `super_admins`, back-office EYWAI admin
- `audit_logs`, `webhook_*` — infra technique
- Détails moteur paie interne (fichiers `calcul_*.py`) — sauf si question data sur bulletins/cumuls

## 7. Cohérence libellés

**Règle** : les libellés du guide = libellés sidebar **exactement**.

Écarts connus à corriger si présents dans `app_knowledge.py` :
- Sidebar : « Avances & acomptes » (pas « Avances sur salaire » seul)
- Sidebar : « Prêts employeur » (module paie workflow)
- Sidebar RH paie : « Calendrier » vs section Gestion « Calendriers » — préciser le contexte
