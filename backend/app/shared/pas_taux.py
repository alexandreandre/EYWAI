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

from typing import Any, Dict, Optional

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


def taux_connu(bloc: Optional[Dict[str, Any]]) -> Optional[float]:
    """Le taux que l'on détient pour ce salarié, ou None si l'on n'en a aucun.

    Un taux se détient de deux façons seulement :
    - **transmis** par la DGFiP — DSN ou compte rendu métier : il porte un type
      de taux, un identifiant ou la période d'où il vient ;
    - **saisi à la main**, case « personnalisé » cochée (`is_personnalise`).

    Un `taux` sans rien de cela n'est pas un taux : c'est la valeur par défaut
    d'un formulaire. La fenêtre de création envoyait `{is_personnalise: false,
    taux: 0}` case décochée, et la fiche renvoyait `taux: 0` à chaque
    enregistrement d'une fiche sans taux (12/10/2026, [B1]) : lu comme un taux
    personnalisé, ce 0 dispensait le salarié de tout prélèvement. Un 0 % transmis
    par la DGFiP, lui, reste un taux.
    """
    if not isinstance(bloc, dict):
        return None
    brut = bloc.get("taux")
    if brut is None or brut == "":
        return None
    try:
        taux = float(brut)
    except (TypeError, ValueError):
        return None
    transmis = bool(
        normaliser(bloc.get("type_taux"))
        or str(bloc.get("identifiant_taux") or "").strip()
        or str(bloc.get("periode") or "").strip()
    )
    if transmis or bloc.get("is_personnalise") is True:
        return taux
    return None


ZONE_METROPOLE = "metropole"
ZONE_ANTILLES_REUNION = "guadeloupe_reunion_martinique"
ZONE_GUYANE_MAYOTTE = "guyane_mayotte"


def zone_du_code_postal(code_postal: Any) -> str:
    """Zone du barème du taux neutre, d'après le code postal de l'établissement.

    Trois zones seulement : métropole, Antilles-Réunion, Guyane-Mayotte.
    L'Alsace-Moselle n'en est pas une (particularité d'assurance maladie, sans
    effet sur l'impôt).
    """
    departement = str(code_postal or "").strip()[:3]
    if departement in ("971", "972", "974"):
        return ZONE_ANTILLES_REUNION
    if departement in ("973", "976"):
        return ZONE_GUYANE_MAYOTTE
    return ZONE_METROPOLE
