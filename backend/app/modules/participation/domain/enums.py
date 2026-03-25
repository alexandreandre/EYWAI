"""
Énumérations du domaine participation (Participation & Intéressement).

Alignées sur le legacy : modes de répartition uniforme / salaire / présence / combinaison.
"""

from enum import Enum


class DistributionMode(str, Enum):
    """Mode de répartition de la participation ou de l'intéressement."""

    UNIFORME = "uniforme"
    SALAIRE = "salaire"
    PRESENCE = "presence"
    COMBINAISON = "combinaison"
