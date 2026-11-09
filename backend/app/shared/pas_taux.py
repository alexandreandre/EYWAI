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

import calendar
import re
from datetime import date, timedelta
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


def terme_de_deux_mois_au_plus(debut: date, fin: date) -> bool:
    """Un contrat dont le terme n'excède pas deux mois, décompté de date à date.

    BOI-IR-PAS-20-20-30-10 § 250 : du 15/01 au 14/03 inclus, deux mois ; au
    15/03, davantage. Un jour de début sans équivalent deux mois plus tard (le
    31/12) fait du dernier jour de ce mois la limite.
    """
    mois, an = debut.month + 2, debut.year
    if mois > 12:
        mois, an = mois - 12, an + 1
    dernier_jour = calendar.monthrange(an, mois)[1]
    if debut.day > dernier_jour:
        limite = date(an, mois, dernier_jour)
    else:
        limite = date(an, mois, debut.day) - timedelta(days=1)
    return fin <= limite


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


# --- Péremption d'un taux personnalisé (01) -------------------------------
# Au-delà de ce nombre de mois, le taux personnalisé en base a de bonnes chances
# d'avoir été remplacé par la DGFiP : la DSN d'un mois est déposée le mois
# suivant, un taux de deux mois est donc le plus récent qu'on puisse détenir en
# régime normal. Sans nouvel envoi, le taux se périme et la grille reprend
# (CGI 1671). Même seuil pour l'écran (statut « À rafraîchir ») et le moteur.
ANCIENNETE_TOLEREE_MOIS = 2

_PERIODE_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def periode_valide(periode: Optional[str]) -> bool:
    return bool(periode) and bool(_PERIODE_RE.match(periode or ""))


def periode_courante(today: Optional[date] = None) -> str:
    d = today or date.today()
    return f"{d.year:04d}-{d.month:02d}"


def ecart_mois(periode: str, reference: str) -> Optional[int]:
    """Nombre de mois entre une période et une référence, None si illisible."""
    if not periode_valide(periode) or not periode_valide(reference):
        return None
    ay, am = int(periode[:4]), int(periode[5:7])
    by, bm = int(reference[:4]), int(reference[5:7])
    return (by - ay) * 12 + (bm - am)


def taux_personnalise_perime(
    bloc: Optional[Dict[str, Any]], reference_periode: Optional[str]
) -> bool:
    """Un taux personnalisé transmis est-il périmé à la période de paie ?

    Vrai seulement pour un taux de type 01 qui porte une période antérieure de
    plus de `ANCIENNETE_TOLEREE_MOIS` mois à la paie. Un taux saisi à la main
    (sans période transmise) n'a pas de date d'envoi : on ne le périme pas. Sans
    période de référence lisible, on ne juge pas non plus.
    """
    if not isinstance(bloc, dict) or not periode_valide(reference_periode):
        return False
    if not est_taux_personnalise(bloc.get("type_taux")):
        return False
    ecart = ecart_mois(str(bloc.get("periode") or ""), reference_periode or "")
    return ecart is not None and ecart > ANCIENNETE_TOLEREE_MOIS
