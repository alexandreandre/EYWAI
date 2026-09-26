# Audit hygiène du dépôt — 28 mai 2026

Suite au plan « hygiène repo EYWAI » : correctifs appliqués sur `main`, puis vérifications locales (miroir CI).

## Changements réalisés

| Commit | Description |
|--------|-------------|
| `8504c3f` | Retrait du suivi Git de `backend/.venv-ci` et `backend/.venv-ci-local` + `.gitignore` |
| `ad0892f` | Suppression `frontend/src/integrations/supabase/` (client + types, clés en dur) |
| `9f296ba` | Ajout `backend/.env.example` + docx déplacés vers `docs/commercial/` |
| `e519b6a` | Suppression `NewEmployeeForm.tsx` (code mort) |
| `b0e8a3c` | `.gitignore` : `openapi-local.json`, `*.local.json` ; lien README |

## Vérifications exécutées (local)

| Contrôle | Résultat | Notes |
|----------|----------|-------|
| `git ls-files backend/.venv-ci*` | **0 fichier** | OK |
| Client Supabase hardcodé absent | **OK** | |
| `frontend/npm run lint` | **OK** (0 erreur) | 393 warnings préexistants |
| `frontend/npm run test` | **OK** | 128 tests, 11 fichiers |
| `frontend/npm run build` | **OK** | ~6 s |
| `verify-pages-imports.mjs` | **OK** | |
| `verify-no-pages-imports-in-ui.mjs` | **OK** | |
| `backend/ruff check` | **Non exécuté** | `ruff` absent du venv local macOS |
| `backend/pytest tests/unit` | **Non exécuté** (local) | Import WeasyPrint : libs système `libgobject` manquantes sur macOS ; la CI Ubuntu installe cairo/pango (voir `.github/workflows/ci.yml`) |
| `backend` smoke `app.main` | **Non exécuté** (local) | Même contrainte WeasyPrint |

**Recommandation** : valider le backend sur GitHub Actions (push) ou en local après `brew install pango cairo` si besoin de pytest/smoke sur Mac.

## Grille « repo professionnel »

| Critère | Statut | Commentaire |
|---------|--------|-------------|
| Pas de venvs / node_modules versionnés | **Oui** | Venvs CI retirés de l’index ; historique Git peut rester volumineux |
| Pas de secrets en dur dans le code actif | **Oui** | Client Supabase frontend supprimé |
| Onboarding env (front + back) | **Oui** | `frontend/.env.example` + `backend/.env.example` |
| CI verte (lint, unit, build) | **Partiel** (local) | Front validé ; back à confirmer en CI |
| Architecture backend modulaire | **Oui** | Inchangé (`app/modules/*`) |
| Couche `@/api/` respectée par les pages | **Partiel** | ~26 pages importent encore `apiClient` directement |
| Fichiers front < 600 lignes | **Non** | `CreateEmployeeForm`, `MedicalFollowUp`, etc. |
| Tests frontend sur UI métier | **Partiel** | 11 fichiers Vitest, surtout `lib/` et lazy imports |
| Racine du repo dépouillée | **Oui** | Docx dans `docs/commercial/` |
| Scalable équipe 3 devs | **Oui** | Conventions, CI, modules ; dette admin `super/` → `eywai/` |

## Verdict

Le dépôt est **propre et professionnel sur l’hygiène Git, la sécurité de base et l’onboarding** après cette passe. Il reste **scalable côté architecture backend** et **prêt pour la livraison continue** côté frontend (build/tests OK).

Ce n’est **pas encore un repo « fini »** sur la dette front (god files, DRY `apiClient` dans les pages, tests UI). Ces sujets relèvent d’un **plan phase 2** (refactors ciblés, pas de réécriture d’historique Git sauf besoin de taille de clone).

## Phase 2 suggérée (hors périmètre)

- Purger l’historique Git des venvs (`git filter-repo`) si le clone devient trop lourd
- Fusionner les deux `YearCalendarView`
- Migrer les pages vers `@/api/*` au fil des touches
- Archiver `backend/tests/integration/legacy/`
- Découper les plus gros composants front (>600 lignes)
