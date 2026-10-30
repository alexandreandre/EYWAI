"""Rubriques permises dans un signalement d'arrêt (04) ou de reprise (05).

Tableau des usages du cahier technique DSN 2026.1 (fin du cahier,
`docs/audit-maji-2026/sources/dsn-cahier-technique-2026.1.txt`) : seules les
rubriques obligatoires ou conditionnelles de la nature s'écrivent ; les autres
y sont interdites, et DSN-VAL refuse le fichier qui les porte.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Mapping

NATURE_ARRET = "04"
NATURE_REPRISE = "05"

_COMMUNES = frozenset(
    """
    S10.G00.00.001 S10.G00.00.002 S10.G00.00.003 S10.G00.00.004 S10.G00.00.005
    S10.G00.00.006 S10.G00.00.007 S10.G00.00.008
    S10.G00.01.001 S10.G00.01.002 S10.G00.01.003 S10.G00.01.004 S10.G00.01.005
    S10.G00.01.006 S10.G00.01.007 S10.G00.01.008 S10.G00.01.009 S10.G00.01.010
    S10.G00.02.001 S10.G00.02.002 S10.G00.02.004 S10.G00.02.005 S10.G00.02.006
    S20.G00.05.001 S20.G00.05.002 S20.G00.05.003 S20.G00.05.004 S20.G00.05.006
    S20.G00.05.007 S20.G00.05.009
    S20.G00.07.001 S20.G00.07.002 S20.G00.07.003 S20.G00.07.004
    S21.G00.06.001 S21.G00.06.002
    S21.G00.11.001 S21.G00.11.003 S21.G00.11.004 S21.G00.11.005 S21.G00.11.006
    S21.G00.11.007
    S21.G00.15.001 S21.G00.15.002 S21.G00.15.003 S21.G00.15.005
    S21.G00.30.001 S21.G00.30.002 S21.G00.30.003 S21.G00.30.004 S21.G00.30.006
    S21.G00.30.019 S21.G00.30.020
    S21.G00.40.001 S21.G00.40.009 S21.G00.40.019
    S21.G00.60.001 S21.G00.60.002 S21.G00.60.003 S21.G00.60.010 S21.G00.60.011
    S21.G00.60.012 S21.G00.60.600
    """.split()
)
#: La subrogation se déclare à l'arrêt, jamais à la reprise.
_SUBROGATION = frozenset(
    {"S21.G00.60.004", "S21.G00.60.005", "S21.G00.60.006", "S21.G00.60.007", "S21.G00.60.008"}
)

PERMISES: Dict[str, FrozenSet[str]] = {
    NATURE_ARRET: _COMMUNES | _SUBROGATION,
    NATURE_REPRISE: _COMMUNES,
}


def filtrer(rubriques: Mapping[str, str], nature: str) -> Dict[str, str]:
    """Les rubriques du bloc permises dans un signalement de cette nature."""
    if nature not in PERMISES:
        raise ValueError(f"Nature de signalement inconnue : {nature}")
    permises = PERMISES[nature]
    return {code: valeur for code, valeur in rubriques.items() if code in permises}
