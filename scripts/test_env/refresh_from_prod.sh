#!/usr/bin/env bash
# Resynchronise l'environnement de test depuis la production.
#
# Sens unique : lit la production, écrit le test. N'exécute jamais d'écriture
# contre la production.
#
# Variables requises :
#   SUPABASE_PROD_READ_URL  connexion de lecture à la production
#   SUPABASE_TEST_DB_URL    connexion à la base de test (écriture)
#   SUPABASE_PROD_REF       référence du projet de production
#   SUPABASE_TEST_REF       référence du projet de test
#
# Variables requises pour la copie Storage (hors --dry-run) :
#   SUPABASE_PROD_URL, SUPABASE_PROD_SERVICE_KEY
#   SUPABASE_TEST_URL, SUPABASE_TEST_SERVICE_KEY
#
# Option --dry-run : vérifie les gardes puis s'arrête sans rien copier.
#
# La production tourne sous PostgreSQL 17 : pg_dump doit être en 17 ou plus,
# un client plus ancien refuse de dumper un serveur plus récent.

set -euo pipefail

: "${SUPABASE_PROD_READ_URL:?SUPABASE_PROD_READ_URL manquant}"
: "${SUPABASE_TEST_DB_URL:?SUPABASE_TEST_DB_URL manquant}"
: "${SUPABASE_PROD_REF:?SUPABASE_PROD_REF manquant}"
: "${SUPABASE_TEST_REF:?SUPABASE_TEST_REF manquant}"

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Garde de destination -----------------------------------------------------
# Deux vérifications indépendantes : la référence déclarée, et l'URL réelle.
# Une seule des deux pourrait être mal renseignée sans que l'autre le soit.
if [ "$SUPABASE_TEST_REF" = "$SUPABASE_PROD_REF" ]; then
  echo "ERREUR : la cible est la production ($SUPABASE_PROD_REF). Abandon." >&2
  exit 1
fi
if [[ "$SUPABASE_TEST_DB_URL" == *"$SUPABASE_PROD_REF"* ]]; then
  echo "ERREUR : l'URL cible désigne la production ($SUPABASE_PROD_REF). Abandon." >&2
  exit 1
fi

echo "Gardes OK : $SUPABASE_PROD_REF (lecture) -> $SUPABASE_TEST_REF (écriture)"
[ "$DRY_RUN" -eq 1 ] && exit 0

: "${SUPABASE_PROD_URL:?SUPABASE_PROD_URL manquant}"
: "${SUPABASE_PROD_SERVICE_KEY:?SUPABASE_PROD_SERVICE_KEY manquant}"
: "${SUPABASE_TEST_URL:?SUPABASE_TEST_URL manquant}"
: "${SUPABASE_TEST_SERVICE_KEY:?SUPABASE_TEST_SERVICE_KEY manquant}"

# --- Version de l'outillage ---------------------------------------------------
PG_MAJOR="$(pg_dump --version | sed -E 's/.* ([0-9]+)\..*/\1/')"
if [ "$PG_MAJOR" -lt 17 ]; then
  echo "ERREUR : pg_dump $PG_MAJOR détecté, 17+ requis (la prod est en PostgreSQL 17)." >&2
  exit 1
fi

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# --- 1. Dump de la production -------------------------------------------------
# public : schéma ET données. Restaurer un dump complet dans une base vidée
# supprime les problèmes d'ordre des clés étrangères et la dérive de schéma.
echo "Dump du schéma public..."
pg_dump "$SUPABASE_PROD_READ_URL" \
  --schema=public --no-owner --no-privileges \
  --file "$WORKDIR/public.sql"

# auth : données seules. Le schéma auth est géré par Supabase et existe déjà
# dans un projet neuf ; le recréer casserait l'authentification. Les sessions et
# jetons de rafraîchissement sont exclus : propres au projet source, invalides
# ailleurs.
echo "Dump des comptes de connexion..."
pg_dump "$SUPABASE_PROD_READ_URL" \
  --schema=auth --data-only --no-owner --no-privileges \
  --exclude-table=auth.sessions \
  --exclude-table=auth.refresh_tokens \
  --exclude-table=auth.mfa_amr_claims \
  --exclude-table=auth.flow_state \
  --file "$WORKDIR/auth.sql"

# --- 2. Décomptes de référence (contrôle anti-copie partielle) ----------------
# Indispensable : un rôle sans BYPASSRLS lit zéro ligne sur une table protégée
# par RLS, sans la moindre erreur. Ce décompte est le seul garde-fou contre un
# environnement de test silencieusement vide.
PROD_COUNT="$(psql "$SUPABASE_PROD_READ_URL" -tAc "select count(*) from public.employees;")"
echo "Production : $PROD_COUNT salariés."
if [ "$PROD_COUNT" -eq 0 ]; then
  echo "ERREUR : 0 salarié lu en production. Lecture tronquée par la RLS ?" >&2
  exit 1
fi

# --- 3. Restauration dans le test --------------------------------------------
echo "Purge de la base de test..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 \
  -c "drop schema if exists public cascade; create schema public;"

echo "Restauration du schéma public..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 -f "$WORKDIR/public.sql"

echo "Restauration des comptes de connexion..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 \
  -c "truncate auth.identities, auth.users cascade;"
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 -f "$WORKDIR/auth.sql"

# --- 4. Neutralisation --------------------------------------------------------
echo "Neutralisation de la base de test..."
psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 -f "$SCRIPT_DIR/neutralize_test_db.sql"

# --- 5. Storage ---------------------------------------------------------------
echo "Copie des fichiers Storage..."
python3 "$SCRIPT_DIR/copy_storage.py"

# --- 6. Contrôle de cohérence -------------------------------------------------
TEST_COUNT="$(psql "$SUPABASE_TEST_DB_URL" -tAc "select count(*) from public.employees;")"
if [ "$PROD_COUNT" != "$TEST_COUNT" ]; then
  echo "ERREUR : $PROD_COUNT salariés en production, $TEST_COUNT en test." >&2
  echo "Copie partielle probable (RLS tronquant la lecture)." >&2
  exit 1
fi
echo "Contrôle OK : $TEST_COUNT salariés copiés."

psql "$SUPABASE_TEST_DB_URL" -v ON_ERROR_STOP=1 -c \
  "insert into public.test_env_refresh_log (finished_at, employees_count)
   values (now(), $TEST_COUNT);"

echo "Resynchro terminée."
