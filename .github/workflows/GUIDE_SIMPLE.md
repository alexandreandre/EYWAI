# Automatisation Git : guide tout simple

Ce texte explique **ce qui tourne tout seul** quand tu travailles sur le projet : sur **ton ordinateur** (hooks) et sur **GitHub** (workflows). Trois blocs, lisibles d'une traite.

---

## 1. Les mots à connaître (30 secondes)

| Mot | En clair |
|-----|----------|
| **Hook** | Un petit script que Git lance **avant** ou **après** une action (ex. avant un `push`). |
| **Workflow** | Une recette enregistrée sur GitHub : « quand X arrive, fais Y ». |
| **CI** | *Continuous integration* : à chaque PR ou push important, la machine vérifie que le code compile et que les tests passent. |

---

## 2. Sur ton PC : le dossier `.husky/`

**Installation (une fois par clone du dépôt)**

1. À la **racine** du projet :
   ```bash
   npm install
   ```
2. Ça active Husky : Git saura qu'il doit lire les fichiers dans `.husky/`.
3. **Backend (recommandé)** : un venv Python avec les deps `backend/requirements*.txt` (dont **ruff**) pour reproduire la CI.

**Ce qui existe chez nous**

| Fichier | Quand ça s'exécute | Ce que ça fait |
|---------|-------------------|----------------|
| `pre-commit` | Avant chaque `git commit` | **lint-staged** : `ruff check --fix` + `ruff format` sur les `.py` stagés du backend, `eslint --fix` sur les `.ts/.tsx` stagés du frontend. |
| `commit-msg` | À chaque `git commit` | Vérifie que le **message** de commit respecte le format conventionnel (ex. `feat(frontend): …`). |
| `pre-push` | À chaque `git push` | **Vide par défaut** : aucune vérif locale n'est lancée, la CI GitHub prend le relais. Pour reproduire la CI en local : `npm run test:prepush`. |

**Commande utile sans push**

- À la racine : `npm run test:prepush` — lance la même suite que la CI (lint + tests unit + build front).
- **Message guidé** : `npm run commit` au lieu de `git commit -m "..."`.

---

## 3. Sur GitHub : le dossier `.github/workflows/`

Trois fichiers :

| Fichier | Nom dans *Actions* | Déclenchement |
|---------|--------------------|---------------|
| `ci.yml` | **CI** | Chaque PR + chaque push sur `main` |
| `pull-request.yml` | **Pull requests** | Chaque PR (zip de contexte) ; *Run workflow* (revue IA) |
| `deploy.yml` | **Deploy** | Après une **CI verte** sur un push `main`, ou *Run workflow* |

### 3.1 CI (`ci.yml`)

**Philosophie : robuste, simple, pas rigide.** Trois jobs principaux :

| Job | Bloquant ? | Ce qui tourne |
|-----|-----------|----------------|
| **Secrets (gitleaks)** | Oui | Scan anti-fuite de secrets dans le diff. |
| **Backend (lint + unit + OpenAPI)** | Oui | Install Python + ruff (info), **smoke import** de l'app, **tests unit** (`pytest tests/unit`, hermétiques, ~2 s, 1700+ tests), génération du fichier OpenAPI (artifact téléchargeable). |
| **Backend integration (info)** | **Non** | `pytest tests/integration` contre le projet Supabase réel. `continue-on-error` : visible dans les logs, **ne bloque ni le merge ni le déploiement**. Skip auto si secrets Supabase absents. |
| **Frontend (lint + build)** | Oui | `npm ci`, `npm run lint`, `npm run build`. |

**Pourquoi cette séparation ?**
- Les **tests unit** sont hermétiques (mocks, pas de DB). Ils tournent en quelques secondes et ne dépendent que du code.
- Les **tests d'intégration** dépendent d'un projet Supabase réel et de paquets système. On les garde pour visibilité, mais on ne les laisse plus bloquer la chaîne : si Supabase est lent ou un secret expire, on continue à pouvoir merger et déployer.
- Les **tests e2e** (`tests/e2e/`) ne tournent jamais en CI — ils sont pour le local.

**Secrets / variables CI**
- **Aucun obligatoire** pour la CI bloquante : les tests unit utilisent des valeurs Supabase factices au besoin.
- *Optionnels (utilisés si présents)* : `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`, `OPENROUTER_API_KEY`. Sans eux, le job `Backend integration (info)` est simplement skippé.

### 3.2 Pull requests (`pull-request.yml`)

Deux comportements dans le même fichier :

1. **Tu ouvres / mets à jour une PR** → un job génère un **artifact** (zip) avec résumé du diff et liste des fichiers.
2. **Tu veux un commentaire IA sur la PR** → *Actions* → **Pull requests** → **Run workflow** → numéro de PR. Nécessite le secret **`CURSOR_API_KEY`**.

### 3.3 Deploy (`deploy.yml`)

**But :** construire les images Docker et les pousser sur Google Cloud Run (staging puis production).

**Enchaînement :** push `main` → **CI** verte → **Deploy** se lance automatiquement (workflow_run). Le checkout et les tags d'images utilisent **le même SHA** que le run CI qui vient de réussir. Tu peux toujours lancer un déploiement à la main via *Run workflow*.

**Jobs :**
1. **Build & push images** : Docker backend + frontend → GCR.
1bis. **DB migrations (`supabase db push`)** : applique les fichiers `supabase/migrations/` sur le projet Supabase **avant** tout déploiement backend. Idempotent (`ADD COLUMN IF NOT EXISTS`, `INSERT … WHERE NOT EXISTS`). Bloquant : staging attend ce job.
2. **Deploy staging** : Cloud Run + smoke tests (`/health`, `/openapi.json`, frontend `/`).
3. **Deploy production** : protégé par l'environnement GitHub `production` (peut exiger une approbation manuelle dans *Settings → Environments*) + smoke tests.

**À configurer (une fois) :**

| Type | Nom | Rôle |
|------|-----|------|
| Secret | `GCP_SA_KEY` | JSON du compte de service GCP. |
| Secret | `SUPABASE_URL`, `SUPABASE_KEY` | Variables passées à Cloud Run au déploiement. |
| Secret | `SUPABASE_DB_URL` | *(Optionnel)* Chaîne Postgres Supabase pour `supabase db push` en CI. Si absent, le job migrations affiche un avertissement et le déploiement continue (schéma appliqué manuellement). |
| Secret | `OPENROUTER_API_KEY` | Clé OpenRouter pour l'IA en prod (copilot, parsing PDF, etc.). Sans elle, l'app tourne mais l'IA renvoie une erreur de configuration. |
| Variable | `GCP_PROJECT_ID` | Projet GCP cible. |
| Variable | `VITE_API_URL` | URL HTTPS publique du backend (utilisée au build de l'image frontend). |
| Variable (optionnel) | `GCP_REGION`, `BACKEND_SERVICE_NAME`, `FRONTEND_SERVICE_NAME` | Surcharge des valeurs par défaut. |
| Variable (optionnel, prod) | `*_PROD` | Surcharge spécifique production. |

Si un secret ou une variable manque, le job `Build` échoue avec un message clair listant les éléments à ajouter dans *Settings → Secrets and variables → Actions*.

Plus de détail infra : voir `DEPLOIEMENT.md` à la racine.

---

## 4. « Presets » : que choisir au quotidien ?

| Tu veux… | Fais ça |
|----------|---------|
| Coder tranquille sur une branche | Rien de spécial : pre-push est vide, la CI fera le boulot. |
| Vérifier comme la CI avant une PR | `npm run test:prepush` à la racine. |
| Voir si ta PR est OK | Ouvre la PR sur GitHub et attends le workflow **CI** au vert. |
| Déployer | Merge sur `main` → attendre **CI** verte → Deploy part tout seul. Sinon, *Run workflow* sur **Deploy**. |
| Aide rédactionnelle sur une PR | *Actions* → **Pull requests** → *Run workflow* + numéro de PR (clé Cursor requise). |

---

## 5. Résumé pour expliquer à quelqu'un qui débute

1. **`npm install` à la racine** → les **hooks** locaux s'activent.
2. **GitHub** lance **CI** sur les PR et sur `main`.
   - Bloquant : lint + tests unit + build (rapide, hermétique).
   - Info : tests intégration (n'empêche jamais de merger).
3. **Deploy** part quand **CI** est verte sur un push `main` (et que GCP est configuré). Staging d'abord, production ensuite (avec gate).
4. En cas de doute sur une erreur : ouvre le run rouge dans *Actions*, lis la dernière étape en rouge — le message indique souvent quoi corriger.
