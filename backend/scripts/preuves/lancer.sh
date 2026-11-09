#!/bin/zsh
# Filet avant/après au bac à sable, en lecture seule (piège à écritures :
# scripts/verification_rgdu/piege.py).
#
# Usage : scripts/preuves/lancer.sh <dossier hors dépôt> [<commit>] [Société ...]
#   copie le backend du commit (HEAD par défaut) dans <dossier>/apres, puis
#   relève les sociétés demandées (défaut : les 4 du filet historique), en parallèle.
# Il faut : BACKEND_ENV (chemin du .env du backend) et VENV_PYTHON (python du venv).
# Comparer ensuite : python scripts/preuves/comparer5.py "<ancien>/apres_*.json" "<dossier>/apres_*.json"
set -e
F=${1:?dossier du filet, hors du dépôt}
C=${2:-HEAD}
shift $(( $# < 2 ? $# : 2 ))
: ${BACKEND_ENV:?chemin du .env du backend}
: ${VENV_PYTHON:?python du venv du backend}
G=${0:A:h}
RACINE=$(git -C "$G" rev-parse --show-toplevel)
SOCIETES=("$@")
(( ${#SOCIETES} )) || SOCIETES=("Colorplast" "Comitech Composite" "MAJI" "Zone 404 Mars")
mkdir -p "$F/apres"
git -C "$RACINE" archive "$C" backend | tar -x -C "$F/apres"
cp "$BACKEND_ENV" "$F/apres/backend/.env"
git -C "$RACINE" rev-parse --short "$C" > "$F/commit.txt"
for soc in "${SOCIETES[@]}"; do
  court=${soc[1,5]}
  court=${court// /_}
  (cd "$F/apres/backend" && PYTHONPATH=. "$VENV_PYTHON" "$G/filet28.py" "$F/apres_$court.json" "$soc" > "$F/apres_$court.log" 2>&1) &
done
wait
echo fini > "$F/fini.txt"
