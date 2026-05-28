#!/usr/bin/env sh
# Reproduction locale de la CI bloquante (.github/workflows/ci.yml).
#
# Bloquant en local (comme en CI) :
#   - Backend : ruff (info), smoke import, pytest tests/unit
#   - Frontend : npm ci + lint + build
#
# Non lancé ici (info / best-effort en CI uniquement) : pytest tests/integration.
# Pour les lancer manuellement : cd backend && python -m pytest tests/integration -v
#
# Variables d'env optionnelles : SUPABASE_URL, SUPABASE_KEY (sinon valeurs factices).

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# Détecter l'interpréteur Python du backend (chemins absolus indispensables :
# après `cd backend`, un chemin relatif serait résolu sous backend/backend/).
py=""
if [ -x "$REPO_ROOT/backend/.venv/bin/python" ]; then
  py="$REPO_ROOT/backend/.venv/bin/python"
elif [ -x "$REPO_ROOT/backend/venv/bin/python" ]; then
  py="$REPO_ROOT/backend/venv/bin/python"
else
  py="python3"
fi

# Fakes Supabase si pas définis (les tests unit n'appellent pas le réseau).
export SUPABASE_URL="${SUPABASE_URL:-https://ci-fake.supabase.co}"
export SUPABASE_KEY="${SUPABASE_KEY:-ci-fake-anon-key}"
export OPENAI_API_KEY="${OPENAI_API_KEY:-sk-ci-fake}"

echo "=== Backend : ruff check (info) ==="
if (cd "$REPO_ROOT/backend" && "$py" -m ruff --version >/dev/null 2>&1); then
  (cd "$REPO_ROOT/backend" && "$py" -m ruff check .) || echo "ruff a remonté des avertissements (non bloquant)."
elif command -v ruff >/dev/null 2>&1; then
  (cd "$REPO_ROOT/backend" && ruff check .) || echo "ruff a remonté des avertissements (non bloquant)."
else
  echo "ruff absent — installation : cd backend && pip install -r requirements-dev.txt"
fi

echo ""
echo "=== Backend : smoke import ==="
(cd "$REPO_ROOT/backend" && "$py" -c "from app.main import app; print('OK', len(app.openapi()['paths']), 'routes')")

echo ""
echo "=== Backend : pytest tests/unit ==="
(cd "$REPO_ROOT/backend" && "$py" -m pytest tests/unit -v --tb=short -p no:cacheprovider)

if [ "${SKIP_GITLEAKS:-}" != "1" ] && command -v gitleaks >/dev/null 2>&1; then
  echo ""
  echo "=== Gitleaks ==="
  gitleaks detect --source "$REPO_ROOT" -v
fi

echo ""
echo "=== Frontend : npm ci + lint + test + build + verify imports ==="
(cd "$REPO_ROOT/frontend" && npm ci)
(cd "$REPO_ROOT/frontend" && npm run lint)
(cd "$REPO_ROOT/frontend" && npm run test)
(cd "$REPO_ROOT/frontend" && VITE_API_URL="${VITE_API_URL:-https://example.com}" npm run build)
(cd "$REPO_ROOT/frontend" && node scripts/verify-pages-imports.mjs)
(cd "$REPO_ROOT/frontend" && node scripts/verify-no-pages-imports-in-ui.mjs)

echo ""
echo "Suite locale (alignée sur la CI bloquante) : OK."
