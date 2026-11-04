"""Forfait annuel en jours propre au salarié (forfait réduit).

Un salarié au forfait jours peut avoir un forfait inférieur à celui de la
société (un jour par semaine : 43 jours par an). Le nombre est porté par la
fiche, `specificites_paie.forfait_annual_days`, la clé que lisent déjà les
congés d'ancienneté comme forfait du salarié. Vide : le forfait de la société.

Pour la réduction générale, le SMIC annuel est « corrigé du rapport entre le
nombre de jours prévu au forfait du salarié, et 218 jours » (BOSS, allègements
généraux, § 860 ; CSS D241-7, IV, 3e alinéa : « dans le cas où ce nombre est
inférieur à 218 »).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

CLE_FORFAIT_INDIVIDUEL = "forfait_annual_days"
#: Au-delà, ce n'est pas un nombre de jours dans l'année : une saisie à reprendre.
JOURS_MAX_SAISISSABLES = 366


def jours_du_forfait_de_la_fiche(specificites_paie: Optional[Dict[str, Any]]) -> Optional[float]:
    """Jours du forfait annuel inscrits sur la fiche, ou None s'il n'y en a pas.

    Une valeur illisible, nulle, négative ou au-delà d'une année arrête le
    calcul (ValueError, rendue à l'écran) : se replier sans le dire sur le
    forfait de la société donnerait une réduction générale fausse.
    """
    if not isinstance(specificites_paie, dict):
        return None
    brute = specificites_paie.get(CLE_FORFAIT_INDIVIDUEL)
    if brute is None or (isinstance(brute, str) and not brute.strip()):
        return None
    try:
        if isinstance(brute, bool):
            raise ValueError
        jours = float(str(brute).strip().replace(",", ".")) if isinstance(brute, str) else float(brute)
    except (TypeError, ValueError):
        raise ValueError(
            f"Nombre de jours du forfait de la fiche illisible : « {brute} ». "
            "Saisissez un nombre de jours par an (par exemple 43), ou laissez la case vide "
            "pour le forfait de la société."
        ) from None
    if jours <= 0 or jours > JOURS_MAX_SAISISSABLES:
        raise ValueError(
            f"Nombre de jours du forfait de la fiche impossible : {brute}. "
            f"Saisissez un nombre de jours par an entre 1 et {JOURS_MAX_SAISISSABLES}, "
            "ou laissez la case vide pour le forfait de la société."
        )
    return jours
