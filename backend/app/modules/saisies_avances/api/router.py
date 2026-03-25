"""
Router API du module saisies_avances.

Délègue toute la logique à la couche application (commands / queries).
Convertit les exceptions applicatives en HTTPException.
Comportement HTTP identique à api/routers/saisies_avances.py.
"""

import traceback
from decimal import Decimal
from typing import List, Optional, Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from app.modules.saisies_avances.application import commands, queries
from app.modules.saisies_avances.application.dto import (
    SaisiesAvancesError,
    UserContext,
)
from app.modules.saisies_avances.schemas import (
    AdvanceAvailableAmount,
    SalaryAdvance,
    SalaryAdvanceCreate,
    SalaryAdvancePayment,
    SalaryAdvancePaymentCreate,
    SalaryAdvanceRepayment,
    SalaryAdvanceReject,
    SalarySeizure,
    SalarySeizureCreate,
    SalarySeizureDeduction,
    SalarySeizureUpdate,
    SeizableAmountCalculation,
    SignedUploadURL,
)

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User


router = APIRouter(
    prefix="/api/saisies-avances",
    tags=["Saisies et Avances"],
)


def _user_ctx(user) -> UserContext:
    return UserContext(user_id=user.id, role=getattr(user, "role", ""))


def _handle_error(e: Exception) -> None:
    if isinstance(e, SaisiesAvancesError):
        raise HTTPException(status_code=e.status_code, detail=e.message)
    traceback.print_exc()
    raise HTTPException(status_code=500, detail=str(e))


# ========== SAISIES SUR SALAIRE ==========


@router.post("/salary-seizures", response_model=SalarySeizure, status_code=201)
async def create_salary_seizure(
    seizure_data: SalarySeizureCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle saisie sur salaire (RH uniquement)."""
    try:
        return commands.create_salary_seizure(seizure_data, current_user.id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.get("/salary-seizures", response_model=List[SalarySeizure])
async def get_salary_seizures(
    employee_id: Optional[str] = Query(None),
    status: Optional[Literal["active", "suspended", "closed"]] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Récupère la liste des saisies avec filtres (RH)."""
    try:
        return queries.get_salary_seizures(employee_id=employee_id, status=status)
    except Exception as e:
        _handle_error(e)


@router.get("/salary-seizures/{seizure_id}", response_model=SalarySeizure)
async def get_salary_seizure(
    seizure_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les détails d'une saisie."""
    try:
        return queries.get_salary_seizure(seizure_id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.patch("/salary-seizures/{seizure_id}", response_model=SalarySeizure)
async def update_salary_seizure(
    seizure_id: str,
    update_data: SalarySeizureUpdate,
    current_user: User = Depends(get_current_user),
):
    """Met à jour une saisie (RH uniquement)."""
    try:
        return commands.update_salary_seizure(seizure_id, update_data)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.delete("/salary-seizures/{seizure_id}", status_code=204)
async def delete_salary_seizure(
    seizure_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime une saisie (RH uniquement)."""
    try:
        commands.delete_salary_seizure(seizure_id)
    except Exception as e:
        _handle_error(e)


@router.post(
    "/salary-seizures/calculate-seizable",
    response_model=SeizableAmountCalculation,
)
async def calculate_seizable(
    net_salary: Decimal = Body(...),
    dependents_count: int = Body(0),
):
    """Calcule la quotité saisissable pour un salaire donné."""
    try:
        return queries.calculate_seizable(net_salary, dependents_count)
    except Exception as e:
        _handle_error(e)


# ========== AVANCES (employé "me") ==========


@router.get(
    "/employees/me/salary-advances",
    response_model=List[SalaryAdvance],
)
async def get_my_salary_advances(
    current_user: User = Depends(get_current_user),
):
    """Récupère mes avances (employé)."""
    try:
        return queries.get_my_salary_advances(str(current_user.id))
    except Exception as e:
        _handle_error(e)


@router.get(
    "/employees/me/advance-available",
    response_model=AdvanceAvailableAmount,
)
async def get_my_advance_available(
    current_user: User = Depends(get_current_user),
):
    """Récupère le montant disponible pour une avance (employé)."""
    try:
        return queries.get_my_advance_available(str(current_user.id))
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


# ========== SAISIES / AVANCES PAR EMPLOYÉ ==========


@router.get(
    "/employees/{employee_id}/salary-seizures",
    response_model=List[SalarySeizure],
)
async def get_employee_salary_seizures(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les saisies d'un employé."""
    try:
        return queries.get_employee_salary_seizures(employee_id)
    except Exception as e:
        _handle_error(e)


# ========== AVANCES SUR SALAIRE ==========


@router.post("/salary-advances", response_model=SalaryAdvance, status_code=201)
async def create_salary_advance(
    advance_data: SalaryAdvanceCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée une demande d'avance (employé ou RH)."""
    try:
        ctx = _user_ctx(current_user)
        return commands.create_salary_advance(advance_data, ctx)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.get("/salary-advances", response_model=List[SalaryAdvance])
async def get_salary_advances(
    employee_id: Optional[str] = Query(None),
    status: Optional[Literal["pending", "approved", "rejected", "paid"]] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Récupère la liste des avances avec filtres."""
    try:
        return queries.get_salary_advances(
            employee_id=employee_id,
            status=status,
        )
    except Exception as e:
        _handle_error(e)


@router.get("/salary-advances/{advance_id}", response_model=SalaryAdvance)
async def get_salary_advance(
    advance_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les détails d'une avance."""
    try:
        return queries.get_salary_advance(advance_id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.patch(
    "/salary-advances/{advance_id}/approve",
    response_model=SalaryAdvance,
)
async def approve_salary_advance(
    advance_id: str,
    current_user: User = Depends(get_current_user),
):
    """Approuve une avance (RH/Manager). Le montant approuvé = montant demandé."""
    try:
        return commands.approve_salary_advance(advance_id, current_user.id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.patch(
    "/salary-advances/{advance_id}/reject",
    response_model=SalaryAdvance,
)
async def reject_salary_advance(
    advance_id: str,
    rejection_data: SalaryAdvanceReject,
    current_user: User = Depends(get_current_user),
):
    """Rejette une avance (RH/Manager)."""
    try:
        return commands.reject_salary_advance(
            advance_id,
            rejection_data.rejection_reason,
        )
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/employees/{employee_id}/salary-advances",
    response_model=List[SalaryAdvance],
)
async def get_employee_salary_advances(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les avances d'un employé."""
    try:
        return queries.get_employee_salary_advances(employee_id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


# ========== INTÉGRATION BULLETINS ==========


@router.get(
    "/payslips/{payslip_id}/deductions",
    response_model=List[SalarySeizureDeduction],
)
async def get_payslip_deductions(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les prélèvements appliqués sur un bulletin."""
    try:
        return queries.get_payslip_deductions(payslip_id)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/payslips/{payslip_id}/advance-repayments",
    response_model=List[SalaryAdvanceRepayment],
)
async def get_payslip_advance_repayments(
    payslip_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les remboursements d'avances appliqués sur un bulletin."""
    try:
        return queries.get_payslip_advance_repayments(payslip_id)
    except Exception as e:
        _handle_error(e)


# ========== PAIEMENTS D'AVANCES ==========


@router.post(
    "/advance-payments/upload-url",
    response_model=SignedUploadURL,
)
async def get_payment_upload_url(
    filename: str = Body(embed=True),
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour uploader une preuve de paiement."""
    try:
        return commands.get_payment_upload_url(filename, current_user.id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.post(
    "/advance-payments",
    response_model=SalaryAdvancePayment,
    status_code=201,
)
async def create_advance_payment(
    payment_data: SalaryAdvancePaymentCreate,
    current_user: User = Depends(get_current_user),
):
    """Crée un paiement d'avance (versement total ou partiel)."""
    try:
        return commands.create_advance_payment(payment_data, current_user.id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.get(
    "/advances/{advance_id}/payments",
    response_model=List[SalaryAdvancePayment],
)
async def get_advance_payments(
    advance_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère tous les paiements d'une avance."""
    try:
        return queries.get_advance_payments(advance_id)
    except Exception as e:
        _handle_error(e)


@router.get("/advance-payments/{payment_id}/proof-url")
async def get_payment_proof_url(
    payment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Génère une URL signée pour télécharger la preuve de paiement."""
    try:
        url = queries.get_payment_proof_url(payment_id)
        return {"url": url}
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.delete("/advance-payments/{payment_id}")
async def delete_advance_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
):
    """Supprime un paiement d'avance."""
    try:
        return commands.delete_advance_payment(payment_id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)
