"""Parts patronales de protection sociale complémentaire d'un bulletin.

Une seule lecture pour deux usages :
- le montant net social, qui les comprend (BOSS, « Montant net social », II.A.1
  et II.C.29 ; arrêté du 25/02/2016 modifié, art. 1er, II, 1°) ;
- la DSN, qui les déclare en autres éléments de revenu brut (S21.G00.54) :
  92 la santé, 93 la prévoyance et la retraite supplémentaire.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple

COTI_SANTE = {"mutuelle", "complementaire_sante"}
COTI_PREVOYANCE_RETRAITE_SUP = {
    "prevoyance",
    "prevoyance_cadre",
    "prevoyance_non_cadre",
    "retraite_sup",
}


def famille_protection_sociale(ligne: Dict[str, Any]) -> str:
    """« sante », « prevoyance » ou « » pour une ligne de cotisation."""
    coti_id = str(ligne.get("coti_id") or "")
    if coti_id in COTI_SANTE:
        return "sante"
    if coti_id in COTI_PREVOYANCE_RETRAITE_SUP:
        return "prevoyance"
    if coti_id:
        return ""
    libelle = str(ligne.get("libelle") or "").lower()
    if "mutuelle" in libelle or "santé" in libelle or "sante" in libelle:
        return "sante"
    if "prévoyance" in libelle or "prevoyance" in libelle or "retraite sup" in libelle:
        return "prevoyance"
    return ""


def parts_patronales_protection_sociale(lignes: Iterable[Dict[str, Any]]) -> Tuple[float, float]:
    """(santé, prévoyance + retraite supplémentaire), parts patronales."""
    sante = prevoyance = 0.0
    for ligne in lignes or []:
        famille = famille_protection_sociale(ligne)
        montant = float(ligne.get("montant_patronal") or 0)
        if famille == "sante":
            sante += montant
        elif famille == "prevoyance":
            prevoyance += montant
    return round(sante, 2), round(prevoyance, 2)
