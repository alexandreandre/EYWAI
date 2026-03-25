#!/usr/bin/env sh
# Propose un découpage en commits plus petits (par zone du dépôt).
# Usage :
#   sh scripts/git-suggest-atomic-commits.sh           # fichiers modifiés vs HEAD
#   sh scripts/git-suggest-atomic-commits.sh --staged  # fichiers déjà stagés
#
# Rien n’est commité automatiquement : copie les blocs et adapte les messages (commitlint).

set -eu

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

mode="work"
for arg in "$@"; do
  case "$arg" in
    --staged) mode="staged" ;;
  esac
done

if [ "$mode" = "staged" ]; then
  echo "=== Fichiers dans l’index (prochain commit) ==="
  list_cmd="git diff --cached --name-only"
else
  echo "=== Fichiers modifiés vs HEAD ==="
  list_cmd="git diff --name-only HEAD"
fi

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
$list_cmd 2>/dev/null | grep -v '^$' > "$tmp" || true

if [ ! -s "$tmp" ]; then
  echo "(aucun fichier)"
  exit 0
fi

python3 - "$tmp" <<'PY'
import sys
from collections import defaultdict
from pathlib import Path


def bucket(p: str) -> str:
    parts = p.split("/")
    if len(parts) < 2:
        return parts[0] if parts else "."
    a, b = parts[0], parts[1]
    if a == "backend":
        if b == "app" and len(parts) >= 4:
            return f"backend/app/{parts[2]}/{parts[3]}"
        if b == "tests":
            return f"backend/tests/{parts[2]}" if len(parts) >= 3 else "backend/tests"
        return f"backend/{b}"
    if a == "frontend":
        if len(parts) >= 3:
            return f"frontend/{parts[1]}/{parts[2]}"
        return f"frontend/{b}"
    return a


path = Path(sys.argv[1])
data = path.read_text(encoding="utf-8").strip().splitlines()
groups = defaultdict(list)
for line in data:
    line = line.strip()
    if not line:
        continue
    groups[bucket(line)].append(line)

for key in sorted(groups):
    files = groups[key]
    print(f"\n--- Groupe : {key} ({len(files)} fichier(s)) ---")
    print("git add \\")
    for i, f in enumerate(files):
        tail = " \\" if i < len(files) - 1 else ""
        print(f'  "{f}"{tail}')
    hint = key.split("/")[-1].replace("-", "")[:24] or "ci"
    print(
        f'git commit -m "feat({hint}): description courte"\n'
        "  # Ajuster type (fix/chore/…) et scope autorisé (commitlint.config.cjs)\n"
    )
PY
