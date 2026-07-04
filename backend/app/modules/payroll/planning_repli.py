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


def reel_heures_avec_repli_planning_si_sans_pointage(
    prevu_data: List[Dict[str, Any]],
    reel_data: List[Dict[str, Any]],
    *,
    annee: int,
    mois: int,
) -> List[Dict[str, Any]]:
    """
    Contrat heures : sans pointage fiable sur le mois, reprend les heures prévues
    (jours « travail ») pour éviter des retenues d'absence fictives.

    Les heures reprises alimentent le compteur hebdomadaire au niveau du planning
    prévu (pas d'heures sup. inventées au-delà de ce que le pointage réel aurait
    produit sur les jours prévus).
    """
    if not mois_sans_pointage(reel_data, annee=annee, mois=mois):
        return reel_data

    prevu_travail = [
        j
        for j in prevu_data
        if _dans_mois(j, annee=annee, mois=mois)
        and j.get("type") == "travail"
        and (j.get("heures_prevues") or 0) > 0
    ]
    if not prevu_travail:
        return reel_data

    log_payroll_debug(
        logger,
        f"INFO: Aucun pointage heures sur {mois:02d}/{annee} — repli sur le planning "
        f"({len(prevu_travail)} jour(s) travaillés, heures prévues).",
    )

    reel_hors_mois = [j for j in reel_data if not _dans_mois(j, annee=annee, mois=mois)]
    reel_synthese = [
        {
            "annee": j.get("annee", annee),
            "mois": j["mois"],
            "jour": j["jour"],
            "type": "travail",
            "heures_faites": float(j.get("heures_prevues") or 0),
            "source_repli_planning": True,
        }
        for j in prevu_travail
    ]
    return reel_hors_mois + reel_synthese


def appliquer_repli_sans_pointage_par_mois(
    planned_data_all_months: List[Dict[str, Any]],
    actual_data_all_months: List[Dict[str, Any]],
    year_months: List[tuple[int, int]],
    *,
    is_forfait_jour: bool = False,
) -> List[Dict[str, Any]]:
    """Enrichit le calendrier réel avec un repli planning pour chaque mois sans pointage."""
    result = list(actual_data_all_months)
    for annee, mois in year_months:
        prevu_m = [
            e
            for e in planned_data_all_months
            if e.get("annee") == annee and e.get("mois") == mois
        ]
        reel_m = [e for e in result if e.get("annee") == annee and e.get("mois") == mois]
        reel_other = [
            e for e in result if not (e.get("annee") == annee and e.get("mois") == mois)
        ]
        if is_forfait_jour:
            updated = reel_forfait_avec_repli_planning_si_sans_pointage(
                prevu_m, reel_m, annee=annee, mois=mois
            )
        else:
            updated = reel_heures_avec_repli_planning_si_sans_pointage(
                prevu_m, reel_m, annee=annee, mois=mois
            )
        result = reel_other + updated
    return result
