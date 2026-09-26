# Recette post-refonte architecture — 2026-05-28

## Synthèse

| Champ | Valeur |
|-------|--------|
| **Verdict** | **GO conditionnel** |
| **Branche** | `chore/pages-reorg` |
| **Commit** | `010dbc5` (au moment de la recette) |
| **Environnement** | Supabase staging (`backend/.env`) |

**GO conditionnel** : les gates bloquantes automatisées (1–3, 5) sont vertes. La gate 4 (intégration) présente 25 échecs à analyser (souvent auth / mocks / données staging). La gate 6 (UI manuelle complète) nécessite une validation humaine en local ; les proxies automatisés (e2e smoke, lazyPages, `/me` badgeuse) sont OK.

---

## Gates

| Gate | Résultat | Détail |
|------|----------|--------|
| **0** Préparation | OK | venv Python, `node_modules`, `.env` staging (SUPABASE_*). Pas de `TEST_USER_*` dans `.env`. |
| **1** CI locale miroir | OK | 1889 tests unit backend ; 128 tests vitest ; lint/build ; verify imports. Script `run-local-ci-suite.sh` aligné CI (test + verify). |
| **2** Garde-fous archi | OK | 5 passed — allowlist routers vide, résolution employé unique. |
| **3** Unit complet | OK | 1889 passed (après correctifs tests/métier listés ci-dessous). |
| **4** Intégration staging | **17 failed** | 1153 passed, 16 skipped (`--import-mode=importlib`). Legacy : erreur collecte `test_login.py`. |
| **5** E2E smoke | OK | 54 passed (`test_smoke_global`, `test_smoke_modules`, `test_auth_flow`, `cross_module`). |
| **6** Manuel UI | **Partiel** | Voir matrice §6 — proxies auto OK ; parcours navigateur complet à faire par l’équipe. |
| **7** OpenAPI + rapport | OK | `backend/openapi-local.json` généré (~1,6 Mo). |

---

## Correctifs appliqués pendant la recette

| Fichier / zone | Correction |
|----------------|------------|
| `tests/unit/employees/test_employee_profile_access.py` | Import depuis `api.deps` |
| `tests/unit/absences/test_me_router_resolve.py` | Patch `absence_router.*` |
| `tests/unit/absences/test_service.py` | Délégation `resolve_employee_id_for_user_account` + `company_id` |
| `tests/unit/payslips/test_service.py` | `is_platform_admin` dans `UserContext` |
| `tests/unit/uploads/test_service.py` | `is_platform_admin` |
| `tests/unit/collective_agreements/*` | `is_platform_admin` |
| `tests/unit/notifications/test_employee_scope.py` | `patch.object` sur alias |
| `tests/unit/employees/test_my_employee_me_documents.py` | Patch `router_me` / `deps` |
| `app/modules/users/application/commands.py` | Logique `is_revoking_self` (platform admin) |
| `app/modules/rates/application/sync_progress.py` | `enriched.append(item)` manquant |
| `tests/integration/rates/test_api.py` | Import `patch` |
| `scripts/run-local-ci-suite.sh` | `npm run test` + verify scripts |

---

## Gate 4 — Échecs d’intégration (17)

Modules concernés (à trier : régression refonte vs données staging vs tests fragiles) :

- `absences/test_api.py` + `test_wiring.py` (4)
- `access_control/test_api.py` (2)
- `collective_agreements/test_wiring.py` (1)
- `dashboard/test_api.py` (1)
- `participation/test_api.py` (2)
- `payslips/test_api.py` + `test_wiring.py` (6)
- `recruitment/test_repository.py` (1)
- `uploads/test_wiring.py` (2)

Corrigé pendant la recette : mocks `is_platform_admin` (collective_agreements, rates).

**Recommandation** : relancer par module avec `-v` et `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` renseignés dans `.env` pour les tests authentifiés RH.

```bash
cd backend && set -a && . ./.env && set +a
python -m pytest tests/integration/payslips -v --import-mode=importlib
```

---

## Gate 6 — Matrice manuelle (statut)

| ID | Scénario | Proxy auto | Statut manuel |
|----|----------|------------|---------------|
| S01 | Connexion | e2e `test_login_returns_token_or_401` | À valider UI |
| S02 | Switch entreprise | — | À valider UI |
| S03 | Lazy load pages | vitest `lazyPages.imports` + verify scripts | **OK** (auto) |
| S04–S05 | Dashboard RH widgets | — | À valider UI |
| S06–S08 | Employés liste/fiche/docs | intégration employees partielle | À valider UI |
| S09–S20 | Espace collaborateur `/me` | e2e + intégration partielle ; unit `/me` resolve | À valider UI |
| S18–S19 | Badgeuse me | e2e `test_smoke_badgeuse_me_status_today` | À valider UI toggle/QR |
| S21–S24 | Badgeuse RH / forfait | unit badgeuse 28 passed | À valider UI |
| S25–S27 | Recruitment | — | À valider UI |
| S28 | Planning PDF | unit `test_employee_week_pdf` | À valider téléchargement |
| S29–S30 | Admin / super-admin tests | — | À valider UI |
| S31–S32 | Téléchargements blob | `createObjectURL` uniquement dans `downloadBlob.ts` | **OK** (auto) |
| S33–S35 | Régression transversale | e2e cross_module | À valider UI |

**Commandes locales Gate 6** :

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd frontend && VITE_API_URL=http://localhost:8000 npm run dev
```

---

## Contrôles architecture (rappel)

- `ROUTER_PERSISTENCE_ALLOWLIST` : vide
- Résolution employé : canonique `employees/infrastructure/queries.py` + `app/shared/employee_resolution.py`
- Frontend : pas d’import `@/pages/` hors shims

---

## Sign-off

- [x] Gates 1–3 bloquantes OK
- [x] Gate 5 E2E smoke OK sur staging
- [ ] Gate 4 : 17 intégrations en échec — trier avant merge si bloquant métier
- [ ] Gate 6 : matrice UI P0/P1 — validation humaine restante
- [x] Aucun critique détecté sur auth globale (e2e) ni garde-fous archi

**Prochaines actions recommandées**

1. Ajouter `TEST_USER_EMAIL` / `TEST_USER_PASSWORD` dans `.env` staging et relancer `tests/integration`.
2. Parcourir S02, S09–S20, S25 en local (Chrome).
3. Investiguer les 6 échecs `payslips` intégration (souvent liés à `is_platform_admin` / mocks).
