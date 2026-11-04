"""Parts patronales de protection sociale complémentaire d'un bulletin.

Une seule lecture pour deux usages :
- le montant net social, qui ne les comprend qu'à partir des revenus de
  janvier 2027 (voir `DEBUT_PARTS_PATRONALES_DANS_LE_NET_SOCIAL`) ;
- la DSN, qui les déclare en autres éléments de revenu brut (S21.G00.54) :
  92 la santé, 93 la prévoyance et la retraite supplémentaire, quelle que soit
  la période.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, Optional, Tuple

COTI_SANTE = {"mutuelle", "complementaire_sante"}
COTI_PREVOYANCE_RETRAITE_SUP = {
    "prevoyance",
    "prevoyance_cadre",
    "prevoyance_non_cadre",
    "retraite_sup",
}

#: Premier mois de paie dont le montant net social compte les parts patronales
#: de santé, de prévoyance et de retraite supplémentaire.
#:
#: - Revenus de 2026 : elles n'y entrent pas. BOSS, « Montant net social »,
#:   version en vigueur du 01/03/2025 au 01/10/2026 (copie archivée du
#:   08/01/2026), question 13 : les contributions des employeurs de prévoyance
#:   ou de retraite supplémentaire « ne doivent pas être prises en compte dans
#:   le montant net social » ; question 28 : la contribution patronale des
#:   garanties collectives « ne doit pas être intégrée au montant net social ».
#: - Revenus dus à compter du 01/01/2027 : elles y entrent (BOSS en vigueur au
#:   01/11/2026, II.A.1 et question 13). Mise à jour du BOSS du 02/10/2026
#:   (actualités BOSS, « mise-a-jour-montant-net-social-3 »), qui suit un projet
#:   de décret en Conseil d'État encore à publier ; date lue dans Lefebvre
#:   Dalloz (16/10/2026) et LégiSocial (audit du 04/11/2026).
#:
#: À REVÉRIFIER EN DÉCEMBRE 2026 : le décret a-t-il paru ? S'il n'a pas paru, ou
#: s'il fixe une autre date, changer cette seule constante (et ses tests,
#: `test_montant_net_social_parts_patronales.py`).
#: Le versement santé (L. 911-7-1 CSS) suit la même date ; Martine n'en paie pas.
DEBUT_PARTS_PATRONALES_DANS_LE_NET_SOCIAL = date(2027, 1, 1)


def parts_patronales_dans_le_net_social(mois_de_paie: Optional[date]) -> bool:
    """Le montant net social de ce mois de paie compte-t-il les parts patronales ?

    `mois_de_paie` : n'importe quel jour du mois du bulletin. Mois inconnu : la
    règle en vigueur aujourd'hui, elles n'y entrent pas.
    """
    if mois_de_paie is None:
        return False
    return date(mois_de_paie.year, mois_de_paie.month, 1) >= DEBUT_PARTS_PATRONALES_DANS_LE_NET_SOCIAL


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
