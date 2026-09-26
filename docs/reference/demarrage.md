# Démarrer EYWAI en local

Le seul guide de démarrage du dépôt. Il remplace `GUIDE-DEV.md`,
`DEMARRAGE_LOCAL.md` et `docs/LOCAL_SUPABASE.md` (26/09/2026).

## Ce qu'il faut

- **Python 3.11**, la version de la CI et de l'image Docker (3.12 marche aussi
  en local).
- **Node.js 22**, la version de la CI, avec npm.
- Pour une base locale : **Docker Desktop ou OrbStack**, la **CLI Supabase**
  (`brew install supabase/tap/supabase`) et **psql**. Pour vérifier :
  `make check-local-tools`.

## 1. Installer

```bash
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

cd ../frontend
npm install
```

Le venv du backend est toujours `backend/.venv`. Si npm échoue (`ENOTEMPTY`,
« vite: command not found ») : `npm run reinstall` dans `frontend/`.

## 2. Choisir la base

### Option A : Supabase local (conseillée)

Rien ne sort du poste. Une fois l'instantané du schéma pris, elle marche
même quand le Supabase distant est en panne.

1. Démarrer Supabase local : `make supabase-start`.
   API `http://127.0.0.1:54321`, Studio `http://127.0.0.1:54323`,
   Postgres `postgresql://postgres:postgres@127.0.0.1:54322/postgres`.
2. Écrire les fichiers d'environnement : `make env-local-activate`. La commande
   lit les clés locales et réécrit `backend/.env` et `frontend/.env.local`. Les
   anciens fichiers sont copiés en `.backup.<horodatage>` : ils contiennent des
   clés, les supprimer dès qu'ils ne servent plus.
3. La première fois, prendre un instantané du schéma (voir plus bas).
4. Charger la base : `make supabase-local-reset`. La commande vide le schéma
   `public` local, recharge l'instantané, puis `supabase/seed.sql`. Elle ne
   touche jamais un projet distant. Le seed crée un compte RH de démonstration
   (identifiants dans `supabase/seed.sql`).

**Pourquoi un instantané.** Le dépôt n'a pas la migration initiale des tables
historiques (`companies`, `profiles`, `employees`, `user_company_accesses`).
Un `supabase db reset` ne peut donc pas reconstruire la base. On charge à la
place le schéma `public` d'un projet distant, gardé hors git dans
`supabase/local/schema_baseline.sql`. Seul le schéma est copié, pas les données.

```bash
# Sans lier la CLI au projet (préférable) : URI du « Session pooler »,
# copiée depuis le tableau de bord Supabase.
make supabase-dump-prod-schema-db-url DB_URL='postgresql://postgres.<ref>:<mot-de-passe>@<pooler>:5432/postgres'

# Ou en liant la CLI au projet (PROJECT_REF du Makefile par défaut).
make supabase-dump-prod-schema DB_PASSWORD='<mot-de-passe>' PROJECT_REF='<ref>'
```

Le `PROJECT_REF` par défaut du Makefile vise l'ancienne production. Les
migrations plus récentes que l'instantané s'appliquent ensuite à la main :
`psql "postgresql://postgres:postgres@127.0.0.1:54322/postgres" -f supabase/migrations/<fichier>.sql`.

### Option B : un projet distant

Remplir `backend/.env` et `frontend/.env.local` à la main, à partir des modèles.

| Fichier actif | Modèles |
|---|---|
| `backend/.env` | `.env.local.example` (local), `.env.prod.example` (distant), `.env.example` (toutes les variables, commentées) |
| `frontend/.env.local` | `.env.local.example`, `.env.prod.example`, `.env.example` |

**La base de test porte la vraie paie d'un client.** Si le poste la vise :
lecture seule, aucun bulletin régénéré sans accord explicite, et jamais
`pytest tests/integration` (certains fichiers écrivent dans la base dès leur
chargement). Avec `APP_ENV=test`, le backend refuse de démarrer si
`EMAIL_FORCE_REDIRECT_TO` n'est pas posé.

## 3. Lancer

Deux terminaux, depuis la racine :

```bash
make dev-backend    # API : http://localhost:8000 (doc : /docs, santé : /health)
make dev-frontend   # application : http://localhost:8080
```

Sans make : `cd backend && .venv/bin/uvicorn app.main:app --reload` et
`cd frontend && npm run dev`. Arrêter Supabase local : `make supabase-stop`.

## 4. Tester

Tests unitaires du backend (une trentaine de secondes, plus de 6 000 tests) :

```bash
cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit -q -p no:cacheprovider
```

Les valeurs Supabase sont factices : aucun appel réseau. `APP_ENV=prod` évite
deux échecs dus au shell quand celui-ci exporte `APP_ENV=test`.

Frontend, dans `frontend/` :

```bash
npm run test       # vitest
npm run lint
npm run typecheck  # tsc, zéro erreur attendue, bloquant en CI
npm run build
```

- **En une commande**, depuis la racine : `make verifier` (lint, types, tests
  backend et frontend), ou séparément `make test`, `make lint`,
  `make typecheck`. Après une modification du moteur de paie : `make filet`
  (août Colorplast, quelques secondes) ; avant un déploiement :
  `make filet-complet` (janvier à août). Le filet rejoue une photo des entrées
  rangée dans `data/_filet/`, sans accès à la base : zéro écart attendu.
- **Toute la CI en local** : `sh scripts/run-local-ci-suite.sh`. Le script
  réinstalle le frontend (`npm ci`) ; préfixer par `APP_ENV=prod` si le shell
  exporte `APP_ENV=test`.
- **Tests de bout en bout** (Playwright) : `npm run e2e` dans `frontend/`, avec
  `frontend/.env.e2e` (modèle `.env.e2e.example`). Ils visent le site de test
  par défaut. Voir [strategie-qa.md](strategie-qa.md).

## 5. Règles du dépôt

- **Le dépôt est public.** Aucun secret, aucun nom de salarié, aucun montant
  nominatif dans ce qui est commité, messages de commit compris. Les données de
  paie vivent dans `data/`, ignoré par git : voir
  [donnees-locales.md](donnees-locales.md).
- **Commits** au format Conventional Commits, en français :
  `type(portée): résumé` (types dans `commitlint.config.cjs`).
- **Contrôle avant commit** : `.husky/pre-commit` refuse un commit dont un
  fichier Python porte une erreur grave (syntaxe, nom non défini). À activer
  une fois par clone : `git config core.hooksPath .husky`. Le hook
  `prepare-commit-msg` préfixe alors par `chore:` un message qui n'a pas de
  type.
- **Personne ne pousse sur `main` avant la bascule** : le workflow « Deploy »
  redéploierait le site de test avec le code de `main`. Pour déployer une
  branche sur le test : `gh workflow run deploy-test-env.yml --ref <branche>`.
  Voir [guide-environnement-test.md](guide-environnement-test.md) et
  [bascule-production.md](bascule-production.md).
- **Migrations** : jamais `supabase db push` depuis un poste ; la cible
  `make prod-db-push` a été retirée le 26/09/2026. Après `make prod-link` ou `make supabase-dump-prod-schema`, la CLI
  reste liée au projet visé.
- **Outillage** : Claude Code. Commandes (`/commit`, `/debug-local`, `/update`…),
  règles et skills du dépôt sont dans `.claude/` : voir
  [.claude/README.md](../../.claude/README.md). `.cursor/` garde une copie des
  règles pour Cursor.
