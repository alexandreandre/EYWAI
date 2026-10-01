"""État du report d'un net négatif : ce que l'écran doit proposer.

Lecture seule. Le report lui-même est une saisie « sur le net » du mois suivant,
créée, mise à jour ou supprimée par l'API des saisies (contrôle d'accès RH).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from app.modules.payroll.domain.report_nap_negatif import (
    est_un_report,
    mois_reporte,
    mois_suivant,
    nom_du_report,
)


def _saisie_de_report(
    saisies: List[Mapping[str, Any]], annee: int, mois: int
) -> Optional[Dict[str, Any]]:
    for saisie in saisies:
        if not est_un_report(saisie):
            continue
        source = mois_reporte(str(saisie.get("name") or ""))
        if source is not None and source != (annee, mois):
            continue
        return {
            "id": str(saisie.get("id") or ""),
            "name": str(saisie.get("name") or ""),
            "amount": float(saisie.get("amount") or 0.0),
        }
    return None


def construire_etat_du_report(
    payslip_id: str,
    meta: Mapping[str, Any],
    *,
    net_a_payer: Optional[float],
    saisies_mois_suivant: List[Mapping[str, Any]],
    statut_bulletin_suivant: Optional[str],
    mois_suivant_cloture: bool,
) -> Dict[str, Any]:
    annee, mois = int(meta["year"]), int(meta["month"])
    annee_s, mois_s = mois_suivant(annee, mois)
    net = round(float(net_a_payer), 2) if net_a_payer is not None else None
    if mois_suivant_cloture:
        verrou: Optional[str] = "mois_cloture"
    elif statut_bulletin_suivant == "valide":
        verrou = "bulletin_valide"
    else:
        verrou = None
    return {
        "payslip_id": payslip_id,
        "company_id": str(meta.get("company_id") or ""),
        "employee_id": str(meta.get("employee_id") or ""),
        "annee": annee,
        "mois": mois,
        "net_a_payer": net,
        "montant_a_reporter": round(-net, 2) if net is not None and net < 0 else 0.0,
        "annee_suivante": annee_s,
        "mois_suivant": mois_s,
        "nom_du_report": nom_du_report(annee, mois),
        "saisie": _saisie_de_report(list(saisies_mois_suivant), annee, mois),
        "verrou": verrou,
    }


def lire_etat_du_report(payslip_id: str, meta: Mapping[str, Any]) -> Dict[str, Any]:
    from app.modules.payroll.infrastructure.analytics_repository import (
        payroll_analytics_repository,
    )
    from app.modules.payslips.infrastructure.queries import (
        get_payslip_net_a_payer,
        get_payslip_status_for_period,
        get_report_candidates_for_period,
    )

    company_id = str(meta["company_id"])
    employee_id = str(meta["employee_id"])
    annee_s, mois_s = mois_suivant(int(meta["year"]), int(meta["month"]))
    return construire_etat_du_report(
        payslip_id,
        meta,
        net_a_payer=get_payslip_net_a_payer(payslip_id),
        saisies_mois_suivant=get_report_candidates_for_period(
            employee_id, company_id, annee_s, mois_s
        ),
        statut_bulletin_suivant=get_payslip_status_for_period(
            employee_id, company_id, annee_s, mois_s
        ),
        mois_suivant_cloture=payroll_analytics_repository.is_period_closed(
            company_id, annee_s, mois_s
        ),
    )
