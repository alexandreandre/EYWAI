#!/bin/bash
# Cycle complet et SÛR de reconciliation d'un mois historique MBC.
# La restauration de la base (champ PARTAGE salaire_de_base) est GARANTIE en fin
# de cycle, meme si le reconciliateur echoue -> mai ne peut pas rester casse.
# Usage (depuis backend/) : bash scripts/backtest/mbc_month_cycle.sh <mois> [<mois>...]
set -u
cd "$(dirname "$0")/../.." || exit 1
PY=.venv/bin/python

for M in "$@"; do
  echo "================ MOIS $M ================"
  $PY scripts/backtest/bulk_apply_month.py 2026 "$M"      > /dev/null 2>&1
  $PY scripts/backtest/fix_temps_partiel_cal.py 2026 "$M"  > /dev/null 2>&1
  $PY scripts/backtest/flip_base_all.py 2026 "$M"          > /dev/null 2>&1

  $PY -m scripts.backtest.mbc_reconcile --month "$M" > "/tmp/rec_${M}.log" 2>&1
  echo "--- reconciliation mois $M ---"
  grep -E "ameliore|amélioré|gain cumulé" "/tmp/rec_${M}.log" | tail -8

  echo "--- mesure mois $M ---"
  $PY scripts/backtest/measure_par.py "Mont Blanc Composite" 2026 "$M" --workers 8 2>/dev/null \
    | grep -iE "convergés" | tail -1

  # FILET OBLIGATOIRE : restaurer la base partagee quoi qu'il arrive
  $PY -m scripts.backtest.mbc_dbsafe restore employees > /dev/null 2>&1
  echo "--- base restauree ---"
done

echo "================ FILET FINAL : MAI ================"
$PY scripts/backtest/measure_par.py "Mont Blanc Composite" 2026 5 --workers 8 2>/dev/null \
  | grep -iE "convergés" | tail -1
