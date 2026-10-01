"""État du report d'un net négatif : ce que l'écran doit proposer.

Le report est une saisie « sur le net » du mois suivant. La lecture est
partagée par la ligne de paie et l'éditeur. L'écriture passe par l'endpoint
dédié : idempotente, et refusée si le mois suivant est validé ou clos.
Les autres écritures de saisies ne sont pas concernées.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional

from app.modules.monthly_inputs.application.commands import (
    create_employee_monthly_input,
    delete_employee_monthly_input,
    update_monthly_input,
)
from app.modules.monthly_inputs.schemas.requests import MonthlyInputCreate, MonthlyInputUpdate
from app.modules.payroll.domain.report_nap_negatif import (
    CATALOG_PRIME_ID,
    est_un_report,
    message_reports_multiples,
    message_retenue_autre_nom,
    message_verrou_report,
    mois_en_lettres,
    mois_reporte,
    mois_suivant,
    nom_du_report,
    statut_qui_verrouille,
)


class ReportNapRefuse(Exception):
    """Écriture refusée : l'écran affiche la raison, rien n'est écrit."""


@dataclass(frozen=True)
class DecisionEcriture:
    op: Optional[str]
    refus: Optional[str] = None
    saisie_id: Optional[str] = None
    amount: Optional[float] = None
    payload: Optional[Dict[str, Any]] = None


def _resume_saisie(saisie: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(saisie.get("id") or ""),
        "name": str(saisie.get("name") or ""),
        "amount": float(saisie.get("amount") or 0.0),
    }


def classer_saisies(
    saisies: Iterable[Mapping[str, Any]], annee: int, mois: int
) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Reports de ce bulletin, et première retenue « sur le net » qui n'en est pas un."""
    reports: List[Dict[str, Any]] = []
    autres: List[Dict[str, Any]] = []
    for saisie in saisies:
        if est_un_report(saisie):
            source = mois_reporte(str(saisie.get("name") or ""))
            if source is not None and source != (annee, mois):
                continue
            reports.append(_resume_saisie(saisie))
        elif saisie.get("sur_le_net"):
            autres.append(_resume_saisie(saisie))
    return reports, autres[0] if autres else None


def payload_du_report(etat: Mapping[str, Any]) -> Dict[str, Any]:
    annee, mois = int(etat["annee"]), int(etat["mois"])
    return {
        "year": int(etat["annee_suivante"]),
        "month": int(etat["mois_suivant"]),
        "name": str(etat["nom_du_report"]),
        "description": (
            f"Net à payer négatif du bulletin de {mois_en_lettres(annee, mois)}, "
            f"repris sur {mois_en_lettres(int(etat['annee_suivante']), int(etat['mois_suivant']))}."
        ),
        "amount": -float(etat["montant_a_reporter"]),
        "is_socially_taxed": False,
        "is_taxable": False,
        "sur_le_net": True,
        "catalog_prime_id": CATALOG_PRIME_ID,
    }


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
    reports, autre = classer_saisies(saisies_mois_suivant, annee, mois)
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
        "saisie": reports[0] if reports else None,
        "saisies": reports,
        "autre_retenue_sur_le_net": autre,
        "verrou": verrou,
    }


def decider_ecriture_du_report(action: str, etat: Mapping[str, Any]) -> DecisionEcriture:
    verrou = etat.get("verrou")
    annee_s, mois_s = int(etat["annee_suivante"]), int(etat["mois_suivant"])
    if verrou:
        return DecisionEcriture(
            op=None,
            refus=message_verrou_report(
                str(verrou), annee_s, mois_s, supprimer=action == "supprimer"
            ),
        )

    reports = list(etat.get("saisies") or [])
    if not reports and etat.get("saisie"):
        reports = [etat["saisie"]]
    autre = etat.get("autre_retenue_sur_le_net")
    voulu = -float(etat.get("montant_a_reporter") or 0.0)

    if action == "creer":
        if autre and not reports:
            return DecisionEcriture(
                op=None,
                refus=message_retenue_autre_nom(float(autre.get("amount") or 0.0), annee_s, mois_s),
            )
        if len(reports) > 1:
            return DecisionEcriture(
                op=None,
                refus=message_reports_multiples(
                    [float(s.get("amount") or 0.0) for s in reports], annee_s, mois_s
                ),
            )
        if len(reports) == 1:
            existant = reports[0]
            if abs(float(existant.get("amount") or 0.0) - voulu) < 0.005:
                return DecisionEcriture(op="noop", saisie_id=str(existant.get("id") or ""))
            return DecisionEcriture(
                op="mettre_a_jour",
                saisie_id=str(existant.get("id") or ""),
                amount=voulu,
            )
        return DecisionEcriture(op="creer", payload=payload_du_report(etat))

    if action == "mettre_a_jour":
        if len(reports) != 1:
            return DecisionEcriture(
                op=None,
                refus=(
                    message_reports_multiples(
                        [float(s.get("amount") or 0.0) for s in reports], annee_s, mois_s
                    )
                    if len(reports) > 1
                    else "Aucune saisie de report à modifier."
                ),
            )
        return DecisionEcriture(
            op="mettre_a_jour",
            saisie_id=str(reports[0].get("id") or ""),
            amount=voulu,
        )

    if action == "supprimer":
        if len(reports) != 1:
            return DecisionEcriture(
                op=None,
                refus=(
                    message_reports_multiples(
                        [float(s.get("amount") or 0.0) for s in reports], annee_s, mois_s
                    )
                    if len(reports) > 1
                    else "Aucune saisie de report à modifier."
                ),
            )
        return DecisionEcriture(op="supprimer", saisie_id=str(reports[0].get("id") or ""))

    return DecisionEcriture(op=None, refus="Action de report inconnue.")


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


def lire_etats_du_mois(company_id: str, year: int, month: int) -> List[Dict[str, Any]]:
    """Une lecture pour tous les bulletins du mois de paie."""
    from app.modules.payroll.infrastructure.analytics_repository import (
        payroll_analytics_repository,
    )
    from app.modules.payslips.infrastructure.queries import (
        get_payslip_statuses_by_employee_for_period,
        get_payslips_meta_for_period,
        get_report_candidates_for_company_period,
    )

    annee_s, mois_s = mois_suivant(year, month)
    bulletins = get_payslips_meta_for_period(company_id, year, month)
    saisies = get_report_candidates_for_company_period(company_id, annee_s, mois_s)
    statuts = get_payslip_statuses_by_employee_for_period(company_id, annee_s, mois_s)
    cloture = payroll_analytics_repository.is_period_closed(company_id, annee_s, mois_s)

    par_employe: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for saisie in saisies:
        par_employe[str(saisie.get("employee_id") or "")].append(saisie)

    return [
        construire_etat_du_report(
            str(bulletin["id"]),
            bulletin,
            net_a_payer=bulletin.get("net_a_payer"),
            saisies_mois_suivant=par_employe.get(str(bulletin["employee_id"]), []),
            statut_bulletin_suivant=statut_qui_verrouille(
                statuts.get(str(bulletin["employee_id"]), [])
            ),
            mois_suivant_cloture=cloture,
        )
        for bulletin in bulletins
    ]


def executer_report(action: str, payslip_id: str, meta: Mapping[str, Any]) -> Dict[str, Any]:
    """Crée, met à jour ou supprime le report. Relit l'état : un écran périmé est refusé."""
    etat = lire_etat_du_report(payslip_id, meta)
    decision = decider_ecriture_du_report(action, etat)
    if decision.refus:
        raise ReportNapRefuse(decision.refus)
    if decision.op == "noop":
        return etat
    company_id = str(etat["company_id"])
    employee_id = str(etat["employee_id"])
    if decision.op == "creer":
        create_employee_monthly_input(
            employee_id, MonthlyInputCreate(**(decision.payload or {})), company_id
        )
    elif decision.op == "mettre_a_jour":
        if not decision.saisie_id:
            raise ReportNapRefuse("Aucune saisie de report à modifier.")
        update_monthly_input(
            decision.saisie_id,
            MonthlyInputUpdate(amount=decision.amount),
            company_id,
        )
    elif decision.op == "supprimer":
        if not decision.saisie_id:
            raise ReportNapRefuse("Aucune saisie de report à modifier.")
        delete_employee_monthly_input(employee_id, decision.saisie_id, company_id)
    else:
        raise ReportNapRefuse("Action de report inconnue.")
    return lire_etat_du_report(payslip_id, meta)
