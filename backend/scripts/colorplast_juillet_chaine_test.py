"""Regénère juillet 2026 de tous les salariés de Colorplast sur le TEST, après
le retour des maillons de janvier à juin (`colorplast_retour_chaine_test.py`).

Juillet repart du maillon de juin rétabli : Girerd 15 853,64 + 2 668,86 =
18 522,50 de net imposable cumulé, au lieu des 18 435,65 signalés par Gaëlle
le 14/09 (et des 18 682,02 laissés par la regénération annulée). Même chose
pour les autres salariés. Les bulletins eux-mêmes ne changent pas : juillet
a déjà été regénéré avec les règles du jour (fenêtre des variables, bilan
hebdomadaire).

Exécuté en CI via `script-env-test.yml`. Usage : [--apply]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import colorplast_chaine_cumuls_test as chaine  # noqa: E402

chaine.MOIS = range(7, 8)

if __name__ == "__main__":
    raise SystemExit(chaine.main())
