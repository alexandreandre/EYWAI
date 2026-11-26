"""Le bulletin qui reprend un arrêt du bulletin précédent : maintien, IJ, trace.

Les jours reportés arrivent au calendrier du mois marqués `arret_reporte`
(`application/arrets_reportes.py`). La retenue se fait comme pour tout jour
d'arrêt (régularisation antérieure, à ses dates). Le maintien et les IJ se
calculent à part, sur les seuls jours reportés : l'arrêt garde son vrai début,
donc sa carence et le rang de ses jours ; le bulletin du mois ne voit pas ces
jours dans ses propres jours de maintien.

Défaut A11 (jours de maintien relus par leur numéro dans le mois) : les jours
reportés n'entrent jamais dans `jours_maintien` (numéros du mois courant, tirés
du seul arrêt du mois), et le plafond ne regarde que le maintien du mois
(`maintien_verse_du_mois`). Le 29/09 reporté ne se confond pas avec le 29/10.

Pour les deux générateurs, heures et forfait jours.
"""

from __future__ import annotations

import copy
import logging
from datetime import date, timedelta
from typing import Any

from app.modules.payroll.application.arrets_reportes import CLE_TRACE

logger = logging.getLogger(__name__)


def _jour(ev: dict[str, Any]) -> date | None:
    try:
        return date.fromisoformat(str(ev.get("date_complete"))[:10])
    except ValueError:
        return None


def jours_reportes_du_calendrier(calendrier: list[dict[str, Any]]) -> list[tuple[date, dict[str, Any]]]:
    jours = []
    for ev in calendrier or []:
        if not ev.get("arret_reporte"):
            continue
        d = _jour(ev)
        if d is not None:
            jours.append((d, ev))
    return sorted(jours, key=lambda x: x[0])


def libelle_des_jours(jours: list[date]) -> str:
    """« du 29/09/26 » ou « du 28/09/26 au 30/09/26 »."""
    if not jours:
        return ""
    debut, fin = min(jours), max(jours)
    if debut == fin:
        return f"du {debut:%d/%m/%y}"
    return f"du {debut:%d/%m/%y} au {fin:%d/%m/%y}"


def maintien_des_arrets_reportes(
    calendrier: list[dict[str, Any]],
    contexte: Any,
    company_id: str | None,
    employee_id: str | None,
) -> dict[str, Any] | None:
    """Maintien et IJ des jours reportés, arrêt par arrêt, sur leurs seules dates."""
    candidats = [(d, ev) for d, ev in jours_reportes_du_calendrier(calendrier) if ev.get("arret_type")]
    if not candidats or not company_id:
        return None
    from app.modules.maintenance_settings.application.queries import (
        get_maintenance_settings,
    )
    from app.modules.payroll.application.planning_apres_sortie import date_de_sortie
    from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien
    from app.modules.payroll.infrastructure.salaires_de_reference import (
        poser_salaires_de_reference,
    )

    from .payslip_run_heures import (
        _arret_de_jours_candidats,
        _regrouper_par_arret,
        arrets_de_l_annee,
    )

    settings = get_maintenance_settings(company_id).model_dump(mode="json")
    sortie = date_de_sortie(((contexte.contrat or {}).get("contrat") or {}).get("date_sortie"))
    resultats: list[tuple[list[date], dict[str, Any]]] = []
    for groupe in _regrouper_par_arret(candidats):
        arret = _arret_de_jours_candidats(groupe, contexte, sortie)
        jours = [d for d, _ in groupe]
        debut, fin = _bornes_du_report(jours)
        # La période du calcul est celle des jours reportés : le moteur la
        # verrait sinon « entièrement en arrêt » et maintiendrait le salaire
        # du mois pour un seul jour. Le mois d'origine entier reste reconnu.
        arret["mois_entier_en_arret"] = (debut, fin) == _mois_civil(jours[0])
        if settings.get("paid_waiting_days_per_year") and employee_id:
            arret["arrets_annee"] = arrets_de_l_annee(str(employee_id), debut.year, debut.month)
        poser_salaires_de_reference(arret, employee_id)
        resultats.append((jours, calculer_maintien(arret, contexte, settings, debut, fin)))
    return {"arrets": resultats}


def _mois_civil(jour: date) -> tuple[date, date]:
    from app.shared.domain.periode_variables import bornes_mois_civil

    return bornes_mois_civil(jour.year, jour.month)


def _bornes_du_report(jours: list[date]) -> tuple[date, date]:
    """Les jours reportés ; le mois civil entier s'ils en couvrent tous les jours ouvrés."""
    debut_mois, fin_mois = _mois_civil(min(jours))
    ouvres = {
        debut_mois + timedelta(days=k)
        for k in range((fin_mois - debut_mois).days + 1)
        if (debut_mois + timedelta(days=k)).weekday() < 5
    }
    if ouvres and ouvres <= set(jours):
        return debut_mois, fin_mois
    return min(jours), max(jours)


def _montant(bloc: dict[str, Any] | None, cle: str) -> float:
    try:
        return float((bloc or {}).get(cle) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def fusionner_le_report(
    principal: dict[str, Any] | None, report: dict[str, Any] | None
) -> dict[str, Any] | None:
    """Le maintien du mois, augmenté de celui des jours reportés.

    Une seule ligne de maintien et une seule ligne d'IJ subrogées au bulletin,
    comme chez Quadra (« Maintien de salaire »). `maintien_verse_du_mois` garde
    la part du mois : c'est elle qui dit si les jours du mois sont maintenus.
    `arrets_reportes` détaille ce qui vient d'un bulletin précédent.
    """
    if not report or not report.get("arrets"):
        return principal
    arrets = report["arrets"]
    if principal is None:
        fusion = copy.deepcopy(arrets[0][1])
        fusion.setdefault("maintien", {})
        fusion.setdefault("ijss", {})
        maintien_du_mois = 0.0
        ijss_du_mois = 0.0
        subrogation = bool(fusion.get("subrogation_active"))
        a_ajouter = arrets[1:]
        detail_premier = [arrets[0]]
    else:
        fusion = copy.deepcopy(principal)
        fusion.setdefault("maintien", {})
        fusion.setdefault("ijss", {})
        maintien_du_mois = _montant(fusion["maintien"], "maintien_verse")
        ijss_du_mois = _montant(fusion["ijss"], "ijss_theorique")
        subrogation = bool(fusion.get("subrogation_active"))
        a_ajouter = arrets
        detail_premier = []
    maintien_total = _montant(fusion["maintien"], "maintien_verse")
    ijss_total = _montant(fusion["ijss"], "ijss_theorique")
    alertes = list(fusion.get("alertes") or [])
    for jours, res in a_ajouter:
        maintien_total += _montant(res.get("maintien"), "maintien_verse")
        ij = _montant(res.get("ijss"), "ijss_theorique")
        if bool(res.get("subrogation_active")) == subrogation:
            ijss_total += ij
        elif ij > 0:
            alertes.append(
                f"IJ de l'arrêt reporté {libelle_des_jours(jours)} non reprises au bulletin : "
                "la subrogation n'est pas la même que celle de l'arrêt du mois."
            )
        alertes.extend(a for a in res.get("alertes") or [] if a not in alertes)
    fusion["maintien"]["maintien_verse"] = round(maintien_total, 2)
    fusion["maintien"]["maintien_verse_du_mois"] = round(maintien_du_mois, 2)
    fusion["ijss"]["ijss_theorique"] = round(ijss_total, 2)
    fusion["ijss"]["ijss_theorique_du_mois"] = round(ijss_du_mois, 2)
    fusion["alertes"] = alertes
    fusion["arrets_reportes"] = [
        {
            "du": min(jours).isoformat(),
            "au": max(jours).isoformat(),
            "maintien_verse": round(_montant(res.get("maintien"), "maintien_verse"), 2),
            "ijss_theorique": round(_montant(res.get("ijss"), "ijss_theorique"), 2),
            "subrogation_active": bool(res.get("subrogation_active")),
        }
        for jours, res in detail_premier + list(a_ajouter)
    ]
    return fusion


def appliquer_le_maintien_reporte(
    resultats_maintien: dict[str, Any] | None,
    calendrier: list[dict[str, Any]],
    contexte: Any,
    company_id: str | None,
    employee_id: str | None,
) -> dict[str, Any] | None:
    """Le maintien du mois, fusionné avec celui des jours reportés s'il y en a."""
    if not jours_reportes_du_calendrier(calendrier):
        return resultats_maintien
    try:
        report = maintien_des_arrets_reportes(calendrier, contexte, company_id, employee_id)
    except Exception:
        logger.exception("Maintien de l'arrêt reporté non calculé (company_id=%s)", company_id)
        from app.modules.payroll.engine.replis import (
            CODE_REPLI_MAINTIEN,
            signaler_repli,
        )

        signaler_repli(contexte, CODE_REPLI_MAINTIEN)
        return resultats_maintien
    return fusionner_le_report(resultats_maintien, report)


def trace_des_arrets(
    calendrier: list[dict[str, Any]], debut: date, fin: date
) -> dict[str, Any]:
    """Les jours d'arrêt que ce bulletin a traités, et ceux qu'il reprend.

    `jours_comptes` : chaque jour calendaire d'un arrêt présent au calendrier
    du bulletin dans sa période, week-ends compris (de son vrai début à sa vraie
    fin, bornés à la période). Un jour absent de cette liste n'était pas connu
    quand le bulletin a été calculé : le bulletin suivant le reprend.
    """
    comptes: set[date] = set()
    reportes: dict[date, str] = {}
    for ev in calendrier or []:
        if not str(ev.get("type") or "").startswith("arret") and not ev.get("date_debut_arret_reel"):
            continue
        d = _jour(ev)
        if d is None:
            continue
        if ev.get("arret_reporte"):
            reportes[d] = str(ev.get("absence_id") or "")
            continue
        if ev.get("is_regularisation_anterieure") or not (debut <= d <= fin):
            continue
        comptes.add(d)
        try:
            vrai_debut = date.fromisoformat(str(ev.get("date_debut_arret_reel"))[:10])
            vraie_fin = date.fromisoformat(
                str(ev.get("date_fin_arret_reel") or ev.get("date_debut_arret_reel"))[:10]
            )
        except ValueError:
            continue
        jour = max(vrai_debut, debut)
        while jour <= min(vraie_fin, fin):
            comptes.add(jour)
            jour += timedelta(days=1)
    return {
        "jours_comptes": [j.isoformat() for j in sorted(comptes)],
        "reportes": [
            {"date": j.isoformat(), "absence_id": reportes[j]} for j in sorted(reportes)
        ],
    }


def poser_la_trace(
    bulletin: dict[str, Any], calendrier: list[dict[str, Any]], debut: date, fin: date
) -> None:
    """Posée seulement s'il y a un arrêt : un bulletin sans arrêt n'en dit rien."""
    trace = trace_des_arrets(calendrier, debut, fin)
    if trace["jours_comptes"] or trace["reportes"]:
        bulletin[CLE_TRACE] = trace


__all__ = [
    "appliquer_le_maintien_reporte",
    "fusionner_le_report",
    "jours_reportes_du_calendrier",
    "libelle_des_jours",
    "maintien_des_arrets_reportes",
    "poser_la_trace",
    "trace_des_arrets",
]
