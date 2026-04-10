#!/usr/bin/env sh
# Pre-push : aucune vérif locale — la CI GitHub (.github/workflows) s’exécute sur le push.
# Pour reproduire l’ancienne suite en local : sh scripts/run-local-ci-suite.sh

set -eu
cd "$(git rev-parse --show-toplevel)"
exit 0
