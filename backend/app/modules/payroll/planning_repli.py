"""Helpers pointage absent : éviter absences fictives sans inventer d'heures sup."""

from __future__ import annotations

from typing import Any, Dict, List

from app.core.logging import get_logger, log_payroll_debug

logger = get_logger("modules.payroll.planning_repli")


def _dans_mois(j: Dict[str, Any], *, annee: int, mois: int) -> bool:
    return j.get("mois") == mois and j.get("annee", annee) == annee


def mois_sans_pointage(
    reel_data: List[Dict[str, Any]],
    *,
    annee: int,
    mois: int,
) -> bool:
    """Vrai si aucune heure/jour pointé sur le mois (calendrier réel vide ou nul)."""
    reel_mois = [j for j in reel_data if _dans_mois(j, annee=annee, mois=mois)]
    return not any((j.get("heures_faites") or 0) > 0 for j in reel_mois)


def reel_forfait_avec_repli_planning_si_sans_pointage(
    prevu_data: List[Dict[str, Any]],
    reel_data: List[Dict[str, Any]],
    *,
    annee: int,
    mois: int,
) -> List[Dict[str, Any]]:
    """
    Forfait jour : sans pointage, reprend les jours prévus (0/1).

    En heures, ne pas réinjecter le planning : cela créerait des HS/HC fictives.
    """
    if not mois_sans_pointage(reel_data, annee=annee, mois=mois):
        return reel_data

    prevu_travail = [
        j
        for j in prevu_data
        if _dans_mois(j, annee=annee, mois=mois)
        and j.get("type") == "travail"
        and (j.get("heures_prevues") or 0) >= 1
    ]
    if not prevu_travail:
        return reel_data

    log_payroll_debug(
        logger,
        f"INFO: Aucun pointage forfait sur {mois:02d}/{annee} — repli sur le planning "
        f"({len(prevu_travail)} jour(s) travaillés).",
    )

    reel_hors_mois = [j for j in reel_data if not _dans_mois(j, annee=annee, mois=mois)]
    reel_synthese = [
        {
            "annee": j.get("annee", annee),
            "mois": j["mois"],
            "jour": j["jour"],
            "type": "reel",
            "heures_faites": 1,
        }
        for j in prevu_travail
    ]
    return reel_hors_mois + reel_synthese
