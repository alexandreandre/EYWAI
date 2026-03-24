"""
Service applicatif saisies et avances.

Orchestration : domain (règles pures) + infrastructure (repositories, queries, providers).
Comportement strictement identique à l'ancien router.
"""
import os
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.modules.saisies_avances.application.dto import (
    ForbiddenError,
    NotFoundError,
    UserContext,
    ValidationError,
)
from app.modules.saisies_avances.domain.enums import AUTO_APPROVAL_THRESHOLD_EUR
from app.modules.saisies_avances.domain import rules as domain_rules
from app.modules.saisies_avances.infrastructure import mappers as infra_mappers
from app.modules.saisies_avances.infrastructure.providers import advance_payment_storage
from app.modules.saisies_avances.infrastructure.enrichment import (
    get_existing_deduction,
    get_existing_repayment,
    insert_advance_repayment,
    insert_seizure_deduction,
)
from app.modules.saisies_avances.infrastructure.queries import (
    build_advance_available,
    get_advances_to_repay,
    get_payment_with_advance,
    get_proof_file_path,
    get_seizures_for_period,
    list_advances_with_employee_and_remaining_to_pay,
    list_salary_advance_repayments_by_payslip,
    list_salary_seizure_deductions_by_payslip,
    list_seizures_with_employee,
)
from app.modules.saisies_avances.infrastructure.repository import (
    advance_payment_repository,
    advance_repository,
    employee_company_provider,
    seizure_repository,
)
from app.modules.saisies_avances.schemas import (
    AdvanceAvailableAmount,
    SeizableAmountCalculation,
)

AUTO_APPROVAL_THRESHOLD = Decimal(str(AUTO_APPROVAL_THRESHOLD_EUR))


# ----- Requêtes (lecture) -----

def get_salary_seizures(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Liste des saisies avec filtres, enrichie employee_name."""
    return list_seizures_with_employee(employee_id=employee_id, status=status)


def get_salary_seizure(seizure_id: str) -> Dict[str, Any]:
    """Détail d'une saisie."""
    row = seizure_repository.get_by_id(seizure_id)
    if not row:
        raise NotFoundError("Saisie non trouvée.")
    return row


def get_employee_salary_seizures(employee_id: str) -> List[Dict[str, Any]]:
    """Saisies d'un employé."""
    return seizure_repository.list_(employee_id=employee_id)


def get_my_salary_advances(employee_id: str) -> List[Dict[str, Any]]:
    """Avances de l'employé (moi)."""
    return advance_repository.list_(employee_id=employee_id)


def get_my_advance_available(employee_id: str) -> AdvanceAvailableAmount:
    """Montant disponible pour une avance (employé)."""
    today = date.today()
    data = build_advance_available(employee_id, today.year, today.month)
    return infra_mappers.to_advance_available_amount(data)


def get_salary_advances(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Liste des avances avec filtres, enrichie employee_name et remaining_to_pay."""
    return list_advances_with_employee_and_remaining_to_pay(
        employee_id=employee_id, status=status
    )


def get_salary_advance(advance_id: str) -> Dict[str, Any]:
    """Détail d'une avance."""
    row = advance_repository.get_by_id(advance_id)
    if not row:
        raise NotFoundError("Avance non trouvée.")
    return row


def get_employee_salary_advances(employee_id: str) -> List[Dict[str, Any]]:
    """Avances d'un employé (pas 'me')."""
    if employee_id == "me":
        raise NotFoundError("Utilisez /employees/me/salary-advances")
    return advance_repository.list_(employee_id=employee_id)


def get_payslip_deductions(payslip_id: str) -> List[Dict[str, Any]]:
    """Prélèvements appliqués sur un bulletin."""
    return list_salary_seizure_deductions_by_payslip(payslip_id)


def get_payslip_advance_repayments(payslip_id: str) -> List[Dict[str, Any]]:
    """Remboursements d'avances appliqués sur un bulletin."""
    return list_salary_advance_repayments_by_payslip(payslip_id)


def get_advance_payments(advance_id: str) -> List[Dict[str, Any]]:
    """Paiements d'une avance."""
    return advance_payment_repository.list_by_advance_id(advance_id)


def calculate_seizable(
    net_salary: Decimal, dependents_count: int = 0
) -> SeizableAmountCalculation:
    """Quotité saisissable pour un salaire donné (règles pures domain)."""
    seizable = domain_rules.calculate_seizable_amount(net_salary, dependents_count)
    minimum_untouchable = net_salary / Decimal("20")
    majoration = Decimal(dependents_count) * Decimal("104.00")
    adjusted_salary = net_salary + majoration
    return infra_mappers.to_seizable_amount_calculation(
        net_salary=net_salary,
        dependents_count=dependents_count,
        adjusted_salary=adjusted_salary,
        seizable_amount=seizable,
        minimum_untouchable=minimum_untouchable,
    )


# ----- Commandes (écriture) -----

def create_salary_seizure(
    seizure_data: Any, created_by_id: Any
) -> Dict[str, Any]:
    """Crée une saisie sur salaire."""
    company_id = employee_company_provider.get_company_id(seizure_data.employee_id)
    if not company_id:
        raise NotFoundError("Employé non trouvé.")
    db_data = {
        "company_id": company_id,
        "employee_id": seizure_data.employee_id,
        "type": seizure_data.type,
        "reference_legale": seizure_data.reference_legale,
        "creditor_name": seizure_data.creditor_name,
        "creditor_iban": seizure_data.creditor_iban,
        "amount": float(seizure_data.amount) if seizure_data.amount else None,
        "calculation_mode": seizure_data.calculation_mode,
        "percentage": float(seizure_data.percentage) if seizure_data.percentage else None,
        "start_date": seizure_data.start_date.isoformat(),
        "end_date": seizure_data.end_date.isoformat() if seizure_data.end_date else None,
        "priority": seizure_data.priority,
        "document_url": seizure_data.document_url,
        "notes": seizure_data.notes,
        "created_by": created_by_id,
        "status": "active",
    }
    return seizure_repository.create(db_data)


def update_salary_seizure(seizure_id: str, update_data: Any) -> Dict[str, Any]:
    """Met à jour une saisie."""
    update_dict = update_data.model_dump(exclude_none=True)
    if "amount" in update_dict:
        update_dict["amount"] = float(update_dict["amount"])
    if "percentage" in update_dict:
        update_dict["percentage"] = float(update_dict["percentage"])
    if update_dict.get("end_date"):
        update_dict["end_date"] = update_dict["end_date"].isoformat()
    row = seizure_repository.update(seizure_id, update_dict)
    if not row:
        raise NotFoundError("Saisie non trouvée.")
    return row


def delete_salary_seizure(seizure_id: str) -> None:
    """Supprime une saisie."""
    seizure_repository.delete(seizure_id)


def create_salary_advance(advance_data: Any, ctx: UserContext) -> Dict[str, Any]:
    """Crée une demande d'avance (employé ou RH)."""
    if ctx.role == "collaborateur" and advance_data.employee_id != ctx.user_id:
        raise ForbiddenError(
            "Vous ne pouvez créer une demande d'avance que pour vous-même."
        )
    company_id = employee_company_provider.get_company_id(advance_data.employee_id)
    if not company_id:
        raise NotFoundError("Employé non trouvé.")

    if advance_data.employee_id == ctx.user_id:
        data = build_advance_available(
            advance_data.employee_id,
            advance_data.requested_date.year,
            advance_data.requested_date.month,
        )
        available = data["available_amount"]
        if Decimal(str(advance_data.requested_amount)) > available:
            raise ValidationError(
                f"Montant demandé supérieur au disponible ({available}€)"
            )

    is_employee_request = (
        ctx.role == "collaborateur" and advance_data.employee_id == ctx.user_id
    )
    initial_status = domain_rules.initial_advance_status(
        is_employee_request,
        Decimal(str(advance_data.requested_amount)),
        AUTO_APPROVAL_THRESHOLD,
    )

    db_data = {
        "company_id": company_id,
        "employee_id": advance_data.employee_id,
        "requested_amount": float(advance_data.requested_amount),
        "requested_date": advance_data.requested_date.isoformat(),
        "repayment_mode": advance_data.repayment_mode,
        "repayment_months": advance_data.repayment_months,
        "request_comment": advance_data.request_comment,
        "status": initial_status,
        "remaining_amount": 0,
    }
    if initial_status == "approved":
        approved_amount = float(advance_data.requested_amount)
        db_data["approved_amount"] = approved_amount
        db_data["remaining_amount"] = approved_amount
        db_data["approved_by"] = ctx.user_id
        db_data["approved_at"] = datetime.now().isoformat()

    return advance_repository.create(db_data)


def approve_salary_advance(advance_id: str, approved_by_id: Any) -> Dict[str, Any]:
    """Approuve une avance (montant approuvé = montant demandé)."""
    advance = advance_repository.get_by_id(advance_id)
    if not advance:
        raise NotFoundError("Avance non trouvée.")
    if advance["status"] != "pending":
        raise ValidationError("Cette avance ne peut plus être approuvée.")
    requested_amount = float(advance["requested_amount"])
    update_dict = {
        "status": "approved",
        "approved_amount": requested_amount,
        "approved_by": approved_by_id,
        "approved_at": datetime.now().isoformat(),
        "remaining_amount": float(requested_amount),
    }
    if advance.get("repayment_mode"):
        update_dict["repayment_mode"] = advance["repayment_mode"]
    if advance.get("repayment_months"):
        update_dict["repayment_months"] = advance["repayment_months"]
    row = advance_repository.update(advance_id, update_dict)
    if not row:
        raise NotFoundError("Avance non trouvée.")
    return row


def reject_salary_advance(advance_id: str, rejection_reason: str) -> Dict[str, Any]:
    """Rejette une avance."""
    update_dict = {"status": "rejected", "rejection_reason": rejection_reason}
    row = advance_repository.update(advance_id, update_dict)
    if not row:
        raise NotFoundError("Avance non trouvée.")
    return row


def get_payment_upload_url(filename: str, user_id: Any) -> Dict[str, str]:
    """Génère une URL signée pour upload de preuve de paiement."""
    _root, extension = os.path.splitext(filename)
    unique_filename = f"{datetime.now().isoformat()}-{uuid.uuid4().hex}{extension}"
    path = f"{user_id}/{unique_filename}"
    return advance_payment_storage.create_signed_upload_url(path)


def create_advance_payment(payment_data: Any, created_by_id: Any) -> Dict[str, Any]:
    """Crée un paiement d'avance (versement avec preuve)."""
    advance = advance_repository.get_by_id(payment_data.advance_id)
    if not advance:
        raise NotFoundError("Avance non trouvée.")
    company_id = advance["company_id"]
    if advance["status"] not in ("approved", "paid"):
        raise ValidationError(
            "L'avance doit être approuvée avant de pouvoir être versée."
        )
    total_paid = advance_payment_repository.get_total_paid_by_advance_id(
        payment_data.advance_id
    )
    approved_amount = Decimal(str(advance.get("approved_amount", 0)))
    remaining_to_pay = approved_amount - total_paid
    payment_amount = Decimal(str(payment_data.payment_amount))
    if payment_amount > remaining_to_pay:
        raise ValidationError(
            f"Le montant du paiement ({payment_amount}€) dépasse le reste à verser ({remaining_to_pay}€)."
        )
    db_data = {
        "advance_id": payment_data.advance_id,
        "company_id": company_id,
        "payment_amount": float(payment_amount),
        "payment_date": payment_data.payment_date.isoformat(),
        "payment_method": payment_data.payment_method,
        "proof_file_path": payment_data.proof_file_path,
        "proof_file_name": payment_data.proof_file_name,
        "proof_file_type": payment_data.proof_file_type,
        "notes": payment_data.notes,
        "created_by": created_by_id,
    }
    payment = advance_payment_repository.create(db_data)
    new_total_paid = total_paid + payment_amount
    new_remaining = approved_amount - new_total_paid
    update_data = {}
    if new_remaining <= 0:
        update_data["status"] = "paid"
    else:
        update_data["status"] = "approved"
    if total_paid == 0:
        update_data["payment_date"] = payment_data.payment_date.isoformat()
        if payment_data.payment_method:
            update_data["payment_method"] = payment_data.payment_method
    advance_repository.update(payment_data.advance_id, update_data)
    return payment


def get_payment_proof_url(payment_id: str) -> str:
    """URL signée pour télécharger la preuve de paiement."""
    proof_path = get_proof_file_path(payment_id)
    if not proof_path:
        raise NotFoundError("Preuve de paiement non trouvée.")
    return advance_payment_storage.create_signed_download_url(proof_path, 3600)


def delete_advance_payment(payment_id: str) -> Dict[str, bool]:
    """Supprime un paiement d'avance et met à jour le statut de l'avance."""
    payment = get_payment_with_advance(payment_id)
    if not payment:
        raise NotFoundError("Paiement non trouvé.")
    advance = payment.get("advance", {})
    if payment.get("proof_file_path"):
        try:
            advance_payment_storage.remove(payment["proof_file_path"])
        except Exception as e:
            print(f"Erreur suppression fichier: {e}")
    advance_payment_repository.delete(payment_id)
    total_paid = advance_payment_repository.get_total_paid_by_advance_id(
        advance["id"]
    )
    approved_amount = Decimal(str(advance.get("approved_amount", 0)))
    new_remaining = approved_amount - total_paid
    update_data = {}
    if total_paid == 0:
        update_data["status"] = "approved"
        update_data["payment_date"] = None
        update_data["payment_method"] = None
    elif new_remaining <= 0:
        update_data["status"] = "paid"
    else:
        update_data["status"] = "approved"
    advance_repository.update(advance["id"], update_data)
    return {"success": True}


# Enrichissement bulletin (logique autonome, plus de dépendance legacy)
def enrich_payslip(
    payslip_json_data: Dict[str, Any],
    employee_id: str,
    year: int,
    month: int,
    payslip_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Enrichit le bulletin avec saisies et avances (sections retenues_saisies, remboursements_avances).
    Comportement identique au legacy services.saisies_avances_integration.
    """
    net_a_payer = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
    dependents_count = 0

    # 1. Traitement des saisies
    seizures = get_seizures_for_period(employee_id, year, month)
    seizures = domain_rules.apply_priority_order(seizures)
    seizable_amount = domain_rules.calculate_seizable_amount(net_a_payer, dependents_count)

    total_deductions = Decimal("0")
    saisies_appliquees: List[Dict[str, Any]] = []
    remaining_seizable = seizable_amount

    for seizure in seizures:
        if remaining_seizable <= 0:
            break
        if payslip_id:
            existing = get_existing_deduction(seizure["id"], payslip_id)
            if existing:
                continue
        deduction = domain_rules.calculate_seizure_deduction(
            seizure, net_a_payer, remaining_seizable, dependents_count
        )
        if deduction > 0:
            total_deductions += deduction
            remaining_seizable -= deduction
            saisies_appliquees.append({
                "type": seizure.get("type"),
                "montant": float(deduction),
                "creditor_name": seizure.get("creditor_name"),
                "reference": seizure.get("reference_legale"),
            })
            if payslip_id:
                try:
                    insert_seizure_deduction(
                        seizure["id"],
                        payslip_id,
                        year,
                        month,
                        float(payslip_json_data.get("salaire_brut", 0)),
                        float(net_a_payer),
                        float(seizable_amount),
                        float(deduction),
                    )
                except Exception:
                    pass

    # 2. Traitement des avances à rembourser
    synthese_net = payslip_json_data.get("synthese_net", {}) or {}
    acompte_deja_deduit = Decimal(str(synthese_net.get("acompte_verse", 0)))
    if acompte_deja_deduit == 0:
        acompte_deja_deduit = Decimal(str(payslip_json_data.get("acompte_verse", 0)))

    advances = get_advances_to_repay(employee_id, year, month)
    total_repayments = Decimal("0")
    remboursements_appliques: List[Dict[str, Any]] = []

    for advance in advances:
        remaining = Decimal(str(advance.get("remaining_amount", 0)))
        if remaining <= 0:
            continue
        existing_repayment = None
        if payslip_id:
            existing_repayment = get_existing_repayment(advance["id"], payslip_id)
            if existing_repayment:
                repayment_already = Decimal(str(existing_repayment.get("repayment_amount", 0)))
                remaining_after = Decimal(str(existing_repayment.get("remaining_after", 0)))
                remboursements_appliques.append({
                    "montant": float(repayment_already),
                    "date_avance": advance.get("requested_date"),
                    "reste_apres": float(remaining_after),
                })
                total_repayments += repayment_already
                continue
        if advance.get("repayment_mode") == "single":
            repayment_to_use = remaining
        else:
            approved_amount = Decimal(str(advance.get("approved_amount", 0)))
            repayment_months = advance.get("repayment_months", 1)
            repayment_to_use = approved_amount / Decimal(str(repayment_months))
            repayment_to_use = min(repayment_to_use, remaining)
        remaining_after_to_use = remaining - repayment_to_use
        if repayment_to_use > 0:
            total_repayments += repayment_to_use
            remboursements_appliques.append({
                "montant": float(repayment_to_use),
                "date_avance": advance.get("requested_date"),
                "reste_apres": float(remaining_after_to_use),
            })
            try:
                update_data: Dict[str, Any] = {"remaining_amount": float(remaining_after_to_use)}
                if advance.get("status") == "approved":
                    update_data["status"] = "paid"
                    update_data["payment_date"] = date(year, month, 1).isoformat()
                advance_repository.update(advance["id"], update_data)
            except Exception:
                pass
            if payslip_id:
                try:
                    insert_advance_repayment(
                        advance["id"],
                        payslip_id,
                        year,
                        month,
                        float(repayment_to_use),
                        float(remaining_after_to_use),
                    )
                except Exception:
                    pass

    # 3. Enrichissement du payslip_data
    payslip_json_data["retenues_saisies"] = {
        "total_preleve": float(total_deductions),
        "saisies": saisies_appliquees,
    }
    payslip_json_data["remboursements_avances"] = {
        "total_rembourse": float(total_repayments),
        "avances": remboursements_appliques,
    }

    if total_repayments > 0 and acompte_deja_deduit == 0:
        current_net = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
        new_net = current_net - total_repayments
        payslip_json_data["net_a_payer"] = float(max(Decimal("0"), new_net))
    if total_deductions > 0:
        current_net = Decimal(str(payslip_json_data.get("net_a_payer", 0)))
        new_net = current_net - total_deductions
        payslip_json_data["net_a_payer"] = float(max(Decimal("0"), new_net))

    return payslip_json_data
