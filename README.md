# EYWAI

EYWAI est un SIRH avec un moteur de paie français : salariés, contrats,
absences, plannings et pointages, bulletins de paie, DSN, pour plusieurs
sociétés à la fois.

- **Backend** : API FastAPI (Python 3.11), dans `backend/`.
- **Frontend** : React, TypeScript et Vite, dans `frontend/`.
- **Base** : Supabase (PostgreSQL, authentification, stockage des fichiers).
- **Hébergement** : Google Cloud Run, déployé par GitHub Actions.

Une paie réelle tourne aujourd'hui sur le site de test. Il deviendra la
production en octobre ou en novembre 2026 : voir
[docs/reference/bascule-production.md](docs/reference/bascule-production.md).

## Lancer en local

Deux terminaux, ouverts à la racine du dépôt :

```bash
# 1. Backend : http://localhost:8000 (documentation de l'API sur /docs)
cd backend
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload
```

```bash
# 2. Frontend : http://localhost:8080
cd frontend
npm install
npm run dev
```

Il faut d'abord `backend/.env` et `frontend/.env.local`. Le plus simple est une
base Supabase locale : `make supabase-start`, `make env-local-activate`, puis,
après un instantané du schéma, `make supabase-local-reset`. Ensuite
`make dev-backend` et `make dev-frontend`.
Le détail est dans [docs/reference/demarrage.md](docs/reference/demarrage.md).

## Tester

Depuis la racine, les principaux contrôles de la CI :

```bash
cd backend && APP_ENV=prod SUPABASE_URL=https://ci-fake.supabase.co SUPABASE_KEY=ci-fake-anon-key .venv/bin/python -m pytest tests/unit -q -p no:cacheprovider
```

```bash
cd frontend && npm run test && npm run lint && npm run build
```

## Où est quoi

| Dossier | Contenu |
|---|---|
| `backend/` | `app/` (un module par domaine, moteur de paie dans `app/modules/payroll/`), `tests/`, `scripts/` (exploitation, vérifications), `scraping/` (veille des barèmes) |
| `frontend/` | `src/` (l'application), `e2e/` (tests Playwright) |
| `supabase/` | `migrations/` (schéma et droits), `seed.sql` (données de démonstration locales) |
| `docs/` | la documentation : [docs/README.md](docs/README.md) |
| `scripts/` | outils git, CI locale, environnement de test, compte QA |
| `.github/workflows/` | CI et déploiements |
| `.claude/` | commandes, règles et skills Claude Code |
| `landing/` | page vitrine statique |
| `data/` | données de paie réelles, sur le poste seulement, **ignoré par git** |

## Documentation

- [docs/README.md](docs/README.md) : l'index de la documentation.
- [ARCHITECTURE.md](ARCHITECTURE.md) : principes, découpage, CI.
- [backend/app/README.md](backend/app/README.md) : les couches du backend.
- [backend/tests/README.md](backend/tests/README.md) : l'organisation des tests.

## Règles

- **Le dépôt est public.** Aucun secret, aucun nom de salarié, aucun montant
  nominatif dans ce qui est commité, messages de commit compris.
- **Personne ne pousse sur `main` avant la bascule** : le workflow « Deploy »
  redéploierait le site de test avec le code de `main`.
