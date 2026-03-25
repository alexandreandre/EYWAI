#!/usr/bin/env sh
# Aligné sur .github/workflows/ci.yml : Ruff backend, gitleaks (si installé),
# pytest hors e2e, puis npm ci + lint + build frontend.

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

# Détecter l’interpréteur Python du backend (chemins absolus : après `cd backend`,
# un chemin relatif « backend/venv/... » serait résolu sous backend/backend/...).
py=""
if [ -x "$REPO_ROOT/backend/.venv/bin/python" ]; then
  py="$REPO_ROOT/backend/.venv/bin/python"
elif [ -x "$REPO_ROOT/backend/venv/bin/python" ]; then
  py="$REPO_ROOT/backend/venv/bin/python"
else
  py="python3"
fi

echo "=== Backend : ruff check + format (--check) ==="
if ! (cd "$REPO_ROOT/backend" && "$py" -m ruff --version >/dev/null 2>&1) &&
   ! command -v ruff >/dev/null 2>&1; then
  echo "ruff absent — installation minimale (pip + \$py)..." >&2
  "$py" -m pip install -q "ruff>=0.9.0" || {
    echo "Échec pip install ruff. Réessaie : cd backend && pip install -r requirements-dev.txt" >&2
    exit 1
  }
fi
if (cd "$REPO_ROOT/backend" && "$py" -m ruff --version >/dev/null 2>&1); then
  (cd "$REPO_ROOT/backend" && "$py" -m ruff check .)
  (cd "$REPO_ROOT/backend" && "$py" -m ruff format --check .)
elif command -v ruff >/dev/null 2>&1; then
  (cd "$REPO_ROOT/backend" && ruff check .)
  (cd "$REPO_ROOT/backend" && ruff format --check .)
else
  echo "ruff toujours introuvable après pip install." >&2
  exit 1
fi

if [ "${SKIP_GITLEAKS:-}" != "1" ] && command -v gitleaks >/dev/null 2>&1; then
  echo ""
  echo "=== Gitleaks (binaire détecté) ==="
  gitleaks detect --source "$REPO_ROOT" -v
else
  if [ "${SKIP_GITLEAKS:-}" != "1" ]; then
    echo ""
    echo "=== Gitleaks : ignoré (installe gitleaks ou export SKIP_GITLEAKS=1) ==="
  fi
fi

echo ""
echo "=== Backend : pytest (hors e2e) ==="
(cd backend && "$py" -m pytest tests/ -m "not e2e" -v --tb=short)

echo ""
echo "=== Frontend : npm ci + ESLint + build ==="
(cd frontend && npm ci)
(cd frontend && npm run lint)
(cd frontend && VITE_API_URL="${VITE_API_URL:-https://example.com}" npm run build)

echo ""
echo "Suite locale alignée sur la CI : OK."
