#!/usr/bin/env sh
# Appelé par lint-staged avec la liste des fichiers .py stagés (chemins relatifs à la racine).
set -eu
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

py=""
if [ -x "$REPO_ROOT/backend/.venv/bin/python" ]; then
  py="$REPO_ROOT/backend/.venv/bin/python"
elif [ -x "$REPO_ROOT/backend/venv/bin/python" ]; then
  py="$REPO_ROOT/backend/venv/bin/python"
else
  py="python3"
fi

if ! "$py" -m ruff --version >/dev/null 2>&1; then
  echo "pre-commit : installe ruff dans le venv backend (pip install -r requirements-dev.txt) ou : $py -m pip install ruff" >&2
  exit 1
fi

"$py" -m ruff check --fix "$@"
"$py" -m ruff format "$@"
