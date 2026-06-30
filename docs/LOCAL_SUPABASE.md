# Supabase local EYWAI

Ce guide met en place un Supabase de dev local pour travailler meme quand le
projet Supabase cloud est indisponible.

## Principe

Le depot contient deja beaucoup de migrations, mais pas la migration initiale
des tables historiques comme `companies`, `profiles`, `employees` ou
`user_company_accesses`. Un `supabase db reset` classique ne peut donc pas
reconstruire la base depuis zero.

La solution retenue est propre et explicite :

1. Supabase local tourne avec Docker.
2. Le schema `public` courant de prod est dumpe une fois dans un snapshot local
   non versionne : `supabase/local/schema_baseline.sql`.
3. Le reset local recharge ce snapshot, puis applique `supabase/seed.sql`.
4. Les conteneurs sont demarres depuis `.supabase-local`, un runtime genere sans
   migrations, pour ne pas rejouer les migrations historiques incompletes.
5. Les secrets actifs restent dans `backend/.env` et `frontend/.env.local`, non
   versionnes.

## Prerequis

Installer et lancer Docker Desktop ou OrbStack.

La CLI Supabase est installee via Homebrew :

```bash
brew install supabase/tap/supabase
```

Verifier :

```bash
make check-local-tools
```

## Premiere installation locale

1. Copier les environnements locaux :

```bash
make env-local-copy
```

2. Demarrer Supabase local :

```bash
make supabase-start
```

3. Activer les environnements locaux :

```bash
make env-local-activate
```

Cette commande lit les cles de `supabase status`, sauvegarde les fichiers actifs
avec un suffixe `.backup.<timestamp>`, puis regenere :

- `backend/.env`
- `frontend/.env.local`

Pour seulement afficher les cles locales :

```bash
make supabase-status-env
```

4. Generer le snapshot de schema depuis prod :

```bash
make supabase-dump-prod-schema DB_PASSWORD='<mot-de-passe-db-prod>'
```

Par defaut, la commande utilise le project ref prod actuel :

```text
slleauhyjnmiawosvlcg
```

Pour un autre projet :

```bash
make supabase-dump-prod-schema PROJECT_REF='<project-ref>' DB_PASSWORD='<mot-de-passe-db>'
```

Si le dump lie (`--linked`) echoue a cause d'IPv6 ou du pooler, copier dans
Supabase Dashboard l'URI du `Session pooler` en IPv4 puis lancer :

```bash
make supabase-dump-prod-schema-db-url DB_URL='postgresql://postgres.<project-ref>:<mot-de-passe>@aws-1-eu-west-3.pooler.supabase.com:5432/postgres'
```

5. Charger la base locale :

```bash
make supabase-local-reset
```

## Utilisation quotidienne

Demarrer Supabase :

```bash
make supabase-start
```

Lancer le backend :

```bash
make dev-backend
```

Lancer le frontend :

```bash
make dev-frontend
```

Compte local cree par le seed :

```text
Email: rh.dev@eywai.local
Password: DevPassword123!
```

URLs utiles :

```text
Frontend: http://localhost:8080
Backend:  http://localhost:8000
Supabase: http://127.0.0.1:54321
Studio:   http://127.0.0.1:54323
DB:       postgresql://postgres:postgres@127.0.0.1:54322/postgres
```

## Reset local

Pour revenir a une base locale propre :

```bash
make supabase-local-reset
```

Cette commande :

1. drop/recree le schema `public` local ;
2. recharge `supabase/local/schema_baseline.sql` ;
3. applique `supabase/seed.sql`.

Elle ne touche jamais a la prod.

## Passer en prod

Ne jamais copier les `.env` locaux en prod.

Backend prod :

```env
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_KEY=<prod-anon-or-publishable-key>
SUPABASE_SERVICE_KEY=<prod-service-role-key>
SUPABASE_SERVICE_ROLE_KEY=<prod-service-role-key>
FRONTEND_URL=https://<frontend-prod-domain>
```

Frontend prod :

```env
VITE_API_URL=https://<backend-prod-domain>
VITE_SUPABASE_URL=https://<project-ref>.supabase.co
VITE_SUPABASE_PUBLISHABLE_KEY=<prod-anon-or-publishable-key>
VITE_SUPABASE_PROJECT_ID=<project-ref>
```

Lier la CLI a prod :

```bash
make prod-link DB_PASSWORD='<mot-de-passe-db-prod>'
```

Pousser les migrations prod :

```bash
make prod-db-push DB_PASSWORD='<mot-de-passe-db-prod>'
```

Regle importante : on pousse le schema/migrations, pas les donnees locales. Les
donnees metier de prod restent dans Supabase cloud.

## Si Supabase cloud est en incident

Si le snapshot `supabase/local/schema_baseline.sql` existe deja, il n'y a plus
besoin du cloud pour travailler :

```bash
make supabase-start
make env-local-activate
make supabase-local-reset
make dev-backend
make dev-frontend
```

Si le snapshot n'existe pas encore, il faut attendre que le cloud soit
accessible une fois pour le generer.
