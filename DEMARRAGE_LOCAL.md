# Demarrage local EYWAI

Guide rapide pour lancer le projet en local avec Supabase local, backend FastAPI et frontend Vite.

## 1. Demarrer Supabase local

Depuis la racine du projet :

```bash
make supabase-start
```

Verifier que Supabase repond :

```bash
make supabase-status
```

URLs utiles :

```text
Supabase API: http://127.0.0.1:54321
Supabase Studio: http://127.0.0.1:54323
Base Postgres: postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

## 2. Activer les variables locales

```bash
make env-local-activate
```

Cette commande configure :

- `backend/.env`
- `frontend/.env.local`

Elle cree aussi des backups si des fichiers existaient deja.

## 3. Initialiser la base locale

La premiere fois, generer le snapshot du schema depuis Supabase prod :

```bash
make supabase-dump-prod-schema DB_PASSWORD='MOT_DE_PASSE_DB_SUPABASE'
```

Si ta connexion ne supporte pas IPv6, utilise l'URL du `Session pooler` Supabase
en IPv4 :

```bash
make supabase-dump-prod-schema-db-url DB_URL='postgresql://postgres.<project-ref>:<mot-de-passe>@aws-1-eu-west-3.pooler.supabase.com:5432/postgres'
```

Puis charger la base locale :

```bash
make supabase-local-reset
```

Ensuite, pour remettre une base locale propre, seule cette commande suffit :

```bash
make supabase-local-reset
```

## 4. Lancer le backend

Dans un terminal :

```bash
make dev-backend
```

API locale :

```text
http://localhost:8000
```

## 5. Lancer le frontend

Dans un autre terminal :

```bash
make dev-frontend
```

Frontend local :

```text
http://localhost:8080
```

## 6. Se connecter

Compte cree par le seed local :

```text
Email: rh.dev@eywai.local
Mot de passe: DevPassword123!
```

## Commandes quotidiennes

Demarrage classique :

```bash
make supabase-start
make dev-backend
make dev-frontend
```

Reset propre de la base locale :

```bash
make supabase-local-reset
```

Arreter Supabase local :

```bash
make supabase-stop
```

## Repasser sur Supabase prod

Restaurer les backups crees avant l'activation locale, par exemple :

```bash
cp backend/.env.backup.20260630112703 backend/.env
cp frontend/.env.local.backup.20260630112703 frontend/.env.local
```

Ou remplir manuellement :

- `backend/.env` depuis `backend/.env.prod.example`
- `frontend/.env.local` depuis `frontend/.env.prod.example`

## Details

Documentation complete :

```text
docs/LOCAL_SUPABASE.md
```
