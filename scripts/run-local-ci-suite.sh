#!/usr/bin/env sh
# Même périmètre que .github/workflows/ci.yml (pytest hors e2e, ESLint, build Vite).

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$REPO_ROOT"

echo "=== Backend : pytest (hors e2e) ==="
if [ -x backend/venv/bin/python ]; then
  (cd backend && ./venv/bin/python -m pytest tests/ -m "not e2e" -v --tb=short)
else
  (cd backend && python3 -m pytest tests/ -m "not e2e" -v --tb=short)
fi

echo ""
echo "=== Frontend : ESLint + build ==="
(cd frontend && npm run lint)
(cd frontend && VITE_API_URL="${VITE_API_URL:-https://example.com}" npm run build)

echo ""
echo "Suite locale alignée sur la CI : OK."
