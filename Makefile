SHELL := /bin/bash
export PATH := $(HOME)/.orbstack/bin:/opt/homebrew/bin:/usr/local/bin:$(PATH)

PROJECT_REF ?= slleauhyjnmiawosvlcg
LINK_FLAGS ?=
LOCAL_DB_URL ?= postgresql://postgres:postgres@127.0.0.1:54322/postgres
LOCAL_SCHEMA_SNAPSHOT ?= supabase/local/schema_baseline.sql
SUPABASE_SEED ?= supabase/seed.sql
SUPABASE_LOCAL_WORKDIR ?= .supabase-local
DOCKER_BIN := $(shell command -v docker 2>/dev/null || test ! -x "$$HOME/.orbstack/bin/docker" || printf "%s/.orbstack/bin/docker" "$$HOME")

.PHONY: help
help:
	@printf "%s\n" \
		"EYWAI dev commands:" \
		"  make check-local-tools                 Verifie Supabase CLI, Docker et psql" \
		"  make env-local-copy                    Copie les templates local si les .env actifs n'existent pas" \
		"  make env-local-activate                Genere les .env locaux depuis Supabase local avec backup" \
		"  make supabase-start                    Demarre Supabase local" \
		"  make supabase-stop                     Arrete Supabase local" \
		"  make supabase-status                   Affiche les URLs locales" \
		"  make supabase-status-env               Affiche les cles locales a mettre dans les .env" \
		"  make supabase-dump-prod-schema         Dump le schema public prod vers supabase/local/schema_baseline.sql" \
		"  make supabase-local-reset              Recharge le snapshot local puis le seed" \
		"  make dev-backend                       Lance l'API FastAPI locale" \
		"  make dev-frontend                      Lance le frontend Vite local" \
		"  make prod-link                         Lie la CLI au projet Supabase prod" \
		"  make prod-db-push                      Pousse les migrations vers Supabase prod"

.PHONY: check-local-tools
check-local-tools:
	@command -v supabase >/dev/null || (echo "Supabase CLI manquante. Lance: brew install supabase/tap/supabase" && exit 1)
	@command -v psql >/dev/null || (echo "psql manquant. Installe PostgreSQL ou libpq via Homebrew." && exit 1)
	@test -n "$(DOCKER_BIN)" || (echo "Docker/OrbStack manquant ou pas dans le PATH. Installe et demarre Docker Desktop ou OrbStack." && exit 1)
	@"$(DOCKER_BIN)" info >/dev/null 2>&1 || (echo "Docker est installe mais pas demarre." && exit 1)
	@echo "Outils locaux OK."

.PHONY: env-local-copy
env-local-copy:
	@test -f backend/.env || cp backend/.env.local.example backend/.env
	@test -f frontend/.env.local || cp frontend/.env.local.example frontend/.env.local
	@echo "Env local pret. Complete les cles avec: make supabase-status-env"

.PHONY: env-local-activate
env-local-activate:
	@mkdir -p backend frontend
	@ts=$$(date +%Y%m%d%H%M%S); \
	if test -f backend/.env; then cp backend/.env "backend/.env.backup.$$ts"; fi; \
	if test -f frontend/.env.local; then cp frontend/.env.local "frontend/.env.local.backup.$$ts"; fi; \
	status_json=$$(supabase status --workdir "$(SUPABASE_LOCAL_WORKDIR)" -o json); \
	api_url=$$(printf '%s' "$$status_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["API_URL"])'); \
	anon_key=$$(printf '%s' "$$status_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["ANON_KEY"])'); \
	service_key=$$(printf '%s' "$$status_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["SERVICE_ROLE_KEY"])'); \
	publishable_key=$$(printf '%s' "$$status_json" | python3 -c 'import json,sys; data=json.load(sys.stdin); print(data.get("PUBLISHABLE_KEY") or data["ANON_KEY"])'); \
	printf "%s\n" \
		"SUPABASE_URL=$$api_url" \
		"SUPABASE_KEY=$$anon_key" \
		"SUPABASE_SERVICE_KEY=$$service_key" \
		"SUPABASE_SERVICE_ROLE_KEY=$$service_key" \
		"FRONTEND_URL=http://localhost:8080" \
		"LOG_LEVEL=INFO" \
		"NET_ENTREPRISES_ENABLED=false" \
		"ACCOUNTING_API_ENABLED=false" \
		"EYWAI_REPAIR_AGENT_ENABLED=0" > backend/.env; \
	printf "%s\n" \
		"VITE_API_URL=http://localhost:8000" \
		"VITE_SUPABASE_URL=$$api_url" \
		"VITE_SUPABASE_PUBLISHABLE_KEY=$$publishable_key" \
		"VITE_SUPABASE_PROJECT_ID=eywai-local" \
		"VITE_APP_DEBUG=1" > frontend/.env.local; \
	echo "Env locaux actives. Backups crees avec suffixe .backup.$$ts si necessaire."

.PHONY: supabase-start
supabase-start: check-local-tools
	@mkdir -p "$(SUPABASE_LOCAL_WORKDIR)/supabase"
	@cp supabase/config.toml "$(SUPABASE_LOCAL_WORKDIR)/supabase/config.toml"
	supabase start --workdir "$(SUPABASE_LOCAL_WORKDIR)"

.PHONY: supabase-stop
supabase-stop:
	supabase stop --workdir "$(SUPABASE_LOCAL_WORKDIR)"

.PHONY: supabase-status
supabase-status:
	supabase status --workdir "$(SUPABASE_LOCAL_WORKDIR)"

.PHONY: supabase-status-env
supabase-status-env:
	supabase status --workdir "$(SUPABASE_LOCAL_WORKDIR)" -o env

.PHONY: prod-link
prod-link:
	@test -n "$(DB_PASSWORD)" || (echo "DB_PASSWORD requis: make prod-link DB_PASSWORD='...'" && exit 1)
	supabase link --project-ref "$(PROJECT_REF)" --password "$(DB_PASSWORD)" $(LINK_FLAGS)

.PHONY: supabase-dump-prod-schema
supabase-dump-prod-schema:
	@test -n "$(DB_PASSWORD)" || (echo "DB_PASSWORD requis: make supabase-dump-prod-schema DB_PASSWORD='...'" && exit 1)
	@mkdir -p supabase/local
	supabase link --project-ref "$(PROJECT_REF)" --password "$(DB_PASSWORD)" $(LINK_FLAGS)
	supabase db dump --linked --schema public --password "$(DB_PASSWORD)" --file "$(LOCAL_SCHEMA_SNAPSHOT)"

.PHONY: supabase-dump-prod-schema-direct
supabase-dump-prod-schema-direct:
	$(MAKE) supabase-dump-prod-schema DB_PASSWORD="$(DB_PASSWORD)" PROJECT_REF="$(PROJECT_REF)" LINK_FLAGS="--skip-pooler"

.PHONY: supabase-dump-prod-schema-db-url
supabase-dump-prod-schema-db-url:
	@test -n "$(DB_URL)" || (echo "DB_URL requis: make supabase-dump-prod-schema-db-url DB_URL='postgresql://...'" && exit 1)
	@mkdir -p supabase/local
	supabase db dump --db-url "$(DB_URL)" --schema public --file "$(LOCAL_SCHEMA_SNAPSHOT)"
	@echo "Snapshot schema cree: $(LOCAL_SCHEMA_SNAPSHOT)"

.PHONY: supabase-local-reset
supabase-local-reset: check-local-tools
	@test -f "$(LOCAL_SCHEMA_SNAPSHOT)" || (echo "Snapshot manquant: $(LOCAL_SCHEMA_SNAPSHOT). Lance d'abord make supabase-dump-prod-schema DB_PASSWORD='...'" && exit 1)
	psql "$(LOCAL_DB_URL)" -v ON_ERROR_STOP=1 -c "drop schema if exists public cascade; create schema public; grant all on schema public to postgres, anon, authenticated, service_role; alter default privileges in schema public grant all on tables to postgres, anon, authenticated, service_role; alter default privileges in schema public grant all on functions to postgres, anon, authenticated, service_role; alter default privileges in schema public grant all on sequences to postgres, anon, authenticated, service_role;"
	psql "$(LOCAL_DB_URL)" -v ON_ERROR_STOP=1 -f "$(LOCAL_SCHEMA_SNAPSHOT)"
	psql "$(LOCAL_DB_URL)" -v ON_ERROR_STOP=1 -f "$(SUPABASE_SEED)"
	@echo "Base locale rechargee depuis le snapshot + seed."

.PHONY: dev-backend
dev-backend:
	cd backend && venv/bin/uvicorn app.main:app --reload

.PHONY: dev-frontend
dev-frontend:
	cd frontend && npm run dev

.PHONY: prod-db-push
prod-db-push:
	@test -n "$(DB_PASSWORD)" || (echo "DB_PASSWORD requis: make prod-db-push DB_PASSWORD='...'" && exit 1)
	supabase db push --linked --password "$(DB_PASSWORD)"
