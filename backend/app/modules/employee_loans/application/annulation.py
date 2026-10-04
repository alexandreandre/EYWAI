"""Défaire ce qu'un bulletin a retenu sur les prêts : l'échéance redevient due.

Le bulletin retient l'échéance (ligne `employee_loan_repayments`), paie
l'échéance de l'échéancier et baisse le capital restant. Recalculer le bulletin
sans rien rendre perdait l'échéance (déjà payée, plus rien à retenir) ; le
supprimer laissait le capital baissé et, par la clé en cascade, emportait
l'échéance réglée. Défaire rend tout cela, puis le recalcul retient une fois.

Un prêt annulé, mis en défaut ou suspendu depuis ne reprendrait pas l'échéance
au recalcul : la défaire la ferait disparaître. Ces cas sont refusés.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.modules.employee_loans.infrastructure.repository import (
    employee_loan_installments_repository,
    employee_loan_repayments_repository,
    employee_loans_repository,
)
from app.modules.payroll.domain.report_nap_negatif import euros

logger = logging.getLogger(__name__)

# La retenue se refait au recalcul : prêt en cours, ou soldé par ce bulletin.
STATUTS_QUI_REPRENNENT = ("active", "repaid")

_STATUTS_EN_CLAIR = {
    "suspended": "suspendu",
    "cancelled": "annulé",
    "defaulted": "mis en défaut",
    "draft": "repassé en brouillon",
}

_IMPERATIF = {"recalculer": "recalculez", "supprimer": "supprimez"}


def _centimes(valeur: Any) -> Decimal:
    return Decimal(str(valeur or 0)).quantize(Decimal("0.01"))


def refus_de_defaire(payslip_id: str, verbe: str) -> str | None:
    """La phrase qui refuse de défaire les retenues de prêt du bulletin, ou None.

    `verbe` : « recalculer » ou « supprimer ».
    """
    for retenue in employee_loan_repayments_repository.list_by_payslip(payslip_id):
        pret = employee_loans_repository.get_by_id(str(retenue["loan_id"]))
        statut = str((pret or {}).get("status") or "")
        # Un prêt supprimé emporte ses retenues : il n'en reste pas à défaire.
        if not pret or statut in STATUTS_QUI_REPRENNENT:
            continue
        montant = euros(float(_centimes(retenue.get("capital_amount")) + _centimes(retenue.get("interest_amount"))))
        motif = str(pret.get("reason") or "").strip()
        nom = f"le prêt « {motif} »" if motif else "un prêt"
        etat = _STATUTS_EN_CLAIR.get(statut, f"« {statut} »")
        debut = (
            f"Ce bulletin a retenu {montant} € sur {nom}, {etat} depuis : le {verbe} "
            "ferait perdre cette retenue sans pouvoir la refaire."
        )
        if statut == "suspended":
            return (
                f"{debut} Réactivez le prêt, {_IMPERATIF.get(verbe, verbe)} le bulletin, "
                "puis suspendez le prêt de nouveau."
            )
        return f"{debut} Ce bulletin doit rester tel quel."
    return None


def defaire_retenues_du_bulletin(payslip_id: str) -> int:
    """Rend au prêt et à l'échéancier ce que le bulletin a retenu. Rend le nombre
    de retenues défaites ; rien à défaire, 0."""
    retenues = employee_loan_repayments_repository.list_by_payslip(payslip_id)
    for retenue in retenues:
        capital = _centimes(retenue.get("capital_amount"))
        interets = _centimes(retenue.get("interest_amount"))
        loan_id = str(retenue["loan_id"])
        pret = employee_loans_repository.get_by_id(loan_id)
        if pret:
            reste = _centimes(pret.get("remaining_capital")) + capital
            maj: dict[str, Any] = {"remaining_capital": float(reste)}
            if str(pret.get("status") or "") == "repaid" and reste > 0:
                maj["status"] = "active"
            employee_loans_repository.update(loan_id, maj)
        if retenue.get("installment_id"):
            employee_loan_installments_repository.retirer_paiement(
                str(retenue["installment_id"]), float(capital), float(interets), payslip_id
            )
        employee_loan_repayments_repository.delete(str(retenue["id"]))
    employee_loan_installments_repository.detacher_du_bulletin(payslip_id)
    if retenues:
        logger.info(
            "[effets] Bulletin %s : %d retenue(s) de prêt défaite(s).", payslip_id, len(retenues)
        )
    return len(retenues)
