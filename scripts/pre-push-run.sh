#!/usr/bin/env sh
# Pre-push : vérifs complètes sur tout push (toutes branches).
# Contournement ponctuel : HUSKY=0 git push … ou SKIP_PREPUSH=1 git push …

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [ "${SKIP_PREPUSH:-}" = "1" ]; then
  echo "pre-push : SKIP_PREPUSH=1 — saut de la suite."
  exit 0
fi

exec sh "$REPO_ROOT/scripts/run-local-ci-suite.sh"
