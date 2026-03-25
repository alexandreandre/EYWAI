#!/usr/bin/env sh
# Hook pre-push : push vers main → confirmation interactive puis suite CI locale.

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

refs_file=$(mktemp)
trap 'rm -f "$refs_file"' EXIT
cat > "$refs_file"

push_to_main=false
while read -r local_ref local_sha remote_ref remote_sha; do
  case "$remote_ref" in
    refs/heads/main) push_to_main=true ;;
  esac
done < "$refs_file"

if [ "$push_to_main" = false ]; then
  exit 0
fi

if [ -t 1 ] && [ -r /dev/tty ] && [ -w /dev/tty ]; then
  printf "Push vers main détecté. Lancer la suite de tests (backend + frontend) ? [O/n] " > /dev/tty
  read -r reply < /dev/tty || reply=O
  case "${reply:-O}" in
    [nN]|[nN][oO]|non)
      echo "Push sans exécution des tests."
      exit 0
      ;;
  esac
fi

exec sh "$REPO_ROOT/scripts/run-local-ci-suite.sh"
