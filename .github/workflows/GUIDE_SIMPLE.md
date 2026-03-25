# Automatisation Git : guide tout simple

Ce texte explique **ce qui tourne tout seul** quand tu travailles sur le projet : sur **ton ordinateur** (hooks) et sur **GitHub** (workflows). Tu peux le lire comme une histoire en trois blocs.

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

1. À la **racine** du projet (là où il y a le `package.json` qui contient `husky`) :
   ```bash
   npm install
   ```
2. Ça active Husky : Git saura qu’il doit lire les fichiers dans `.husky/`.
3. **Backend** : un venv avec les deps du dossier `backend` (dont **ruff**) pour que le pre-push puisse lancer `ruff` et `pytest` comme en CI.
4. **Gitleaks** (recommandé) : installe le CLI [gitleaks](https://github.com/gitleaks/gitleaks) pour le même scan qu’en CI ; sinon le script affiche un rappel ou tu peux faire `SKIP_GITLEAKS=1 git push`.

**Ce qui existe chez nous**

| Fichier | Quand ça s’exécute | Ce que ça fait |
|---------|-------------------|----------------|
| `commit-msg` | À chaque `git commit` | Vérifie que le **message** de commit respecte le format (ex. `feat(frontend): …`). Si ce n’est pas bon, Git refuse le commit et affiche une erreur claire. |
| `pre-push` | À **chaque** `git push` (toutes branches distantes) | Enchaîne les vérifs **alignées sur `ci.yml`** : **`ruff check`** (backend), **gitleaks** si le binaire est présent, **pytest** hors e2e, puis **`npm ci`** + lint + build (frontend). Le formatage global (`ruff format`) n’est pas exigé ; tu peux le lancer à part sur `backend/`. |

**Contournement ponctuel** (dépannage uniquement) : `SKIP_PREPUSH=1 git push` ou `HUSKY=0 git push`.

**Commande utile sans push**

- À la racine : `npm run test:prepush` — lance la même suite que le hook (pratique avant d’ouvrir une PR).

**Si les hooks ne partent pas**

- **Cause la plus fréquente :** Husky installe les hooks Git dans `.husky/_` (généré au `npm install`, non versionné). Sans **`npm install` à la racine du dépôt** au moins une fois après un clone, `git push` ne lance **pas** le pre-push — aucune erreur, Git ignore simplement le hook manquant.
- Vérifier : `test -f .husky/_/pre-push && echo OK` — si « non », lance `npm install` ou `npm run hooks:install` **depuis la racine** (pas seulement `frontend/`).
- Vérifier que `.husky/pre-push` et `.husky/commit-msg` sont **exécutables** :  
  `chmod +x .husky/pre-push .husky/commit-msg`
- Vérifier `git config core.hooksPath` → doit être `.husky/_`.

---

## 3. Sur GitHub : le dossier `.github/workflows/`

Là il n’y a plus que **3 fichiers** :

| Fichier | Nom affiché dans l’onglet *Actions* | Déclenchement |
|---------|-------------------------------------|---------------|
| `ci.yml` | **CI** | Chaque **pull request** + chaque **push sur `main`** |
| `pull-request.yml` | **Pull requests** | **(A)** chaque PR — zip de contexte ; **(B)** seulement si **tu cliques** *Run workflow* |
| `deploy.yml` | **Deploy** | Après une **CI verte** sur un **push** vers `main`, ou *Run workflow* (manuel) |

### 3.1 CI (`ci.yml`)

**But :** s’assurer que le dépôt reste sain.

- **Secrets** : scan anti-fuite de mots de passe (gitleaks).
- **Backend** : install Python, tests pytest (sans e2e), puis génération d’un fichier **OpenAPI** (tu peux le télécharger en artifact). Les tests qui touchent Supabase utilisent un **vrai projet** : au minimum **`SUPABASE_URL`** et **`SUPABASE_KEY`** (comme le deploy). **`SUPABASE_SERVICE_KEY`** (service_role) est recommandé pour les tests paie / admin. Sans URL joignable, tu obtiens des `ConnectError` en CI. Optionnel : **`OPENAI_API_KEY`** ; sinon une valeur minimale de secours est posée.
- **Frontend** : `npm ci`, lint, build.

Certaines étapes (Ruff, audits npm/pip) sont en **mode info** : elles peuvent être rouges dans les logs sans faire échouer le workflow, tant qu’on ne les a pas rendues bloquantes.

**Où voir le résultat :** GitHub → onglet **Actions** → workflow **CI** → cliquer sur le run.

### 3.2 Pull requests (`pull-request.yml`)

Deux comportements dans **le même fichier**, selon l’événement :

1. **Tu ouvres ou mets à jour une PR**  
   → Un job crée un **artifact** (zip) avec le résumé du diff et la liste des fichiers. Utile pour archiver ou partager le contexte. **Tu n’as rien à cliquer.**

2. **Tu veux un commentaire IA sur une PR**  
   - Prérequis : secret **`ANTHROPIC_API_KEY`** dans *Settings → Secrets and variables → Actions*.
   - *Actions* → **Pull requests** → **Run workflow** → indique le **numéro** de la PR → lancer.  
   → Un commentaire apparaît sur la PR.

### 3.3 Deploy (`deploy.yml`)

**But :** construire les images Docker et les pousser sur Google Cloud Run (staging puis production).

**Enchaînement avec la CI :** le workflow **Deploy** ne part plus directement sur un push vers `main`. Il se déclenche quand le workflow **CI** se termine **avec succès** après un **push** sur **`main`** (les PR seules ne déploient pas, même si la CI est verte). Le checkout et les tags d’images utilisent le **même SHA** que le run CI qui vient de réussir. Tu peux toujours lancer un déploiement à la main via *Run workflow* (`workflow_dispatch`).

**À configurer sur le dépôt GitHub** (une fois, avec quelqu’un qui connaît GCP) :

- **Secret** : `GCP_SA_KEY` (JSON du compte de service).
- **Variable** obligatoire : `GCP_PROJECT_ID`.
- Souvent aussi : `GCP_REGION`, `BACKEND_SERVICE_NAME`, `FRONTEND_SERVICE_NAME`, `VITE_API_URL`, et pour la prod des variantes `*_PROD` si besoin.

L’environnement GitHub **`production`** peut exiger une **approbation** avant le déploiement prod (*Settings → Environments*).

Plus de détail infra : voir **`DEPLOIEMENT.md`** à la racine du dépôt.

---

## 4. « Presets » : que choisir au quotidien ?

| Tu veux… | Fais ça |
|----------|---------|
| Coder tranquille sur une branche | Rien de spécial ; les hooks ne gênent que le commit (message) et le push vers `main`. |
| Vérifier comme la CI avant une PR | `npm run test:prepush` à la racine. |
| Voir si ta PR est OK | Ouvre la PR sur GitHub et attends le workflow **CI** au vert. |
| Déployer | Merge sur `main` puis attendre **CI** au vert (Deploy part juste après) ; ou *Run workflow* sur **Deploy** si tu sais ce que tu fais. |
| Aide rédactionnelle sur une PR | *Actions* → **Pull requests** → *Run workflow* + numéro de PR (clé Anthropic requise). |

---

## 5. Résumé pour expliquer à quelqu’un qui débute

1. **`npm install` à la racine** → les **hooks** locaux s’activent.  
2. **GitHub** lance **CI** tout seul sur les PR et sur `main`.  
3. **Deploy** part quand **CI** est verte sur un **push** vers **`main`** (si GCP est bien configuré), ou au *Run workflow* manuel.  
4. Le reste (**artifact** de PR, **commentaire Claude**) est optionnel et documenté ci-dessus.

En cas de doute sur une erreur précise, ouvre le run rouge dans **Actions** et lis la dernière étape en rouge : le message indique souvent exactement quoi corriger.
