"""Types de taux de prélèvement à la source — rubrique DSN S21.G00.50.007.

Deux familles seulement, et la distinction commande le calcul de la paie :

- le **01** est le taux personnalisé que la DGFiP renvoie dans le compte rendu
  métier ; il vaut jusqu'au prochain envoi, et c'est bien une propriété du
  salarié qu'on a raison de conserver d'un mois sur l'autre ;
- tous les autres codes en usage désignent un **barème par défaut**, que le
  déclarant recalcule chaque mois sur la rémunération versée ce mois-là. Le
  reporter d'un mois sur l'autre est faux : le même salarié passe de 0 % à 5 %
  parce que sa paie a changé, pas parce que l'administration a décidé quoi que
  ce soit.

Nomenclature reprise de la note DGFiP « Projet PAS — application des taux non
personnalisés » publiée par net-entreprises :

    01   taux personnalisé transmis par la DGFiP
    13   barème mensuel métropole
    23   barème mensuel Guadeloupe, Réunion et Martinique
    33   barème mensuel Guyane et Mayotte
    17   barème mathématique sur base mensuelle métropole
    27   barème mathématique sur base mensuelle Guadeloupe, Réunion et Martinique
    37   barème mathématique sur base mensuelle Guyane et Mayotte

Vérifié sur les cinquante DSN réelles des sept sociétés : 233 des 236 lignes de
type 13 tombent au centième sur la grille par défaut appliquée à l'assiette du
versement, ce qui confirme la lecture.
"""

from __future__ import annotations

from typing import Dict, Optional

TYPE_PERSONNALISE = "01"

# Application directe du barème mensuel.
TYPE_BAREME_METROPOLE = "13"
TYPE_BAREME_ANTILLES_REUNION = "23"
TYPE_BAREME_GUYANE_MAYOTTE = "33"

# Barème « proratisé » lorsque la périodicité usuelle de versement n'est pas
# mensuelle : bornes de tranches modifiées, mais même nature de taux.
TYPE_BAREME_MATH_METROPOLE = "17"
TYPE_BAREME_MATH_ANTILLES_REUNION = "27"
TYPE_BAREME_MATH_GUYANE_MAYOTTE = "37"

TYPES_BAREME = frozenset(
    {
        TYPE_BAREME_METROPOLE,
        TYPE_BAREME_ANTILLES_REUNION,
        TYPE_BAREME_GUYANE_MAYOTTE,
        TYPE_BAREME_MATH_METROPOLE,
        TYPE_BAREME_MATH_ANTILLES_REUNION,
        TYPE_BAREME_MATH_GUYANE_MAYOTTE,
    }
)

LIBELLES: Dict[str, str] = {
    TYPE_PERSONNALISE: "Taux personnalisé DGFiP",
    TYPE_BAREME_METROPOLE: "Barème par défaut (métropole)",
    TYPE_BAREME_ANTILLES_REUNION: "Barème par défaut (Guadeloupe, Réunion, Martinique)",
    TYPE_BAREME_GUYANE_MAYOTTE: "Barème par défaut (Guyane, Mayotte)",
    TYPE_BAREME_MATH_METROPOLE: "Barème par défaut proratisé (métropole)",
    TYPE_BAREME_MATH_ANTILLES_REUNION: (
        "Barème par défaut proratisé (Guadeloupe, Réunion, Martinique)"
    ),
    TYPE_BAREME_MATH_GUYANE_MAYOTTE: "Barème par défaut proratisé (Guyane, Mayotte)",
}


def normaliser(type_taux: Optional[str]) -> str:
    return str(type_taux or "").strip()


def est_taux_bareme(type_taux: Optional[str]) -> bool:
    """Le taux vient-il d'une grille recalculée chaque mois ?"""
    return normaliser(type_taux) in TYPES_BAREME


def est_taux_personnalise(type_taux: Optional[str]) -> bool:
    return normaliser(type_taux) == TYPE_PERSONNALISE


def libelle_type(type_taux: Optional[str]) -> str:
    """Libellé lisible, y compris pour un code que la norme ajouterait plus tard."""
    code = normaliser(type_taux)
    if not code:
        return "Origine inconnue"
    return LIBELLES.get(code, f"Type {code}")
