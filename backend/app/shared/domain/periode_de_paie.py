"""
La période de paie d'une société, en un seul endroit.

`parametres_paie` n'est PAS une colonne : c'est une structure assemblée à
partir des colonnes de `companies`. Le module planning l'ignorait et lisait
une colonne `companies.parametres_paie` inexistante ; l'erreur était avalée
par un `try/except`, et les salariés au forfait-jours retombaient
silencieusement sur un découpage au mois calendaire.

C'était sans conséquence tant que toutes les sociétés ayant des forfaits-jours
finissaient leur paie le 31 — ce qui est le cas aujourd'hui, mais tient du
hasard. Colorplast finit le 4.

Toute lecture de la période de paie passe désormais par ici.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

#: Valeurs de repli, alignées sur celles du générateur de bulletins.
JOUR_DE_FIN_PAR_DEFAUT = 4
OCCURRENCE_PAR_DEFAUT = -2

#: Colonnes de `companies` nécessaires pour construire la période.
COLONNES_REQUISES = ("paie_jour_de_fin", "paie_occurrence")


def periode_de_paie_depuis_societe(societe: Optional[Dict[str, Any]]) -> Dict[str, int]:
    """`{"jour_de_fin", "occurrence"}` à partir d'une ligne `companies`."""
    ligne = societe or {}
    jour = ligne.get("paie_jour_de_fin")
    occurrence = ligne.get("paie_occurrence")
    return {
        "jour_de_fin": (
            int(jour) if isinstance(jour, (int, float)) else JOUR_DE_FIN_PAR_DEFAUT
        ),
        "occurrence": (
            int(occurrence)
            if isinstance(occurrence, (int, float))
            else OCCURRENCE_PAR_DEFAUT
        ),
    }


def parametres_paie_depuis_societe(
    societe: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Le bloc `parametres_paie` attendu par le moteur de forfait-jours."""
    return {"periode_de_paie": periode_de_paie_depuis_societe(societe)}
