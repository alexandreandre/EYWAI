#!/usr/bin/env sh
# Normalise les messages fournis via git commit -m "..." pour qu’ils passent commitlint.
# Ex. "test" → "chore: test". Les messages déjà au format Conventional Commits sont inchangés.
# Ne touche pas aux merges / squash (Git passe un autre « source » au hook).

set -eu

MSG_FILE="${1:-}"
SOURCE="${2:-}"

if [ -z "$MSG_FILE" ] || [ ! -f "$MSG_FILE" ]; then
  exit 0
fi

case "$SOURCE" in
  merge|squash|commit) exit 0 ;;
esac

# Seulement les messages explicites (-m / -F), pas l’éditeur vide / template.
if [ "$SOURCE" != "message" ]; then
  exit 0
fi

first=$(head -n 1 "$MSG_FILE" | tr -d '\r')
if [ -z "$first" ]; then
  exit 0
fi

# Déjà au format type(scope)?!?: sujet
if printf '%s\n' "$first" | grep -qE \
  '^(feat|fix|chore|docs|refactor|perf|test|build|ci|revert)(\([^)]+\))?(!)?: .+'; then
  exit 0
fi

tmp="${MSG_FILE}.tmp$$"
{
  printf 'chore: %s\n' "$first"
  tail -n +2 "$MSG_FILE"
} >"$tmp"
mv "$tmp" "$MSG_FILE"
