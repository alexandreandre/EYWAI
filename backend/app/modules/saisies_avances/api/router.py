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
    AcomptePrimeReconcile,
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
from app.modules.access_control.application.service import access_control_service
from app.modules.users.schemas.responses import User


router = APIRouter(
    prefix="/api/saisies-avances",
    tags=["Saisies et Avances"],
)

_ERR_RH_REQUIRED = "Accès réservé aux RH et administrateurs."


def _user_ctx(user) -> UserContext:
    return UserContext(
        user_id=user.id,
        role=user.role,
        active_company_id=user.active_company_id,
    )


def _require_rh_or_admin(current_user: User) -> None:
    if current_user.is_platform_admin:
        return
    active_company_id = current_user.active_company_id
    if not active_company_id or not current_user.has_rh_access_in_company(active_company_id):
        raise HTTPException(status_code=403, detail=_ERR_RH_REQUIRED)


def _active_company_id(current_user: User) -> str:
    cid = current_user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active sélectionnée.")
    return str(cid)


_ADVANCES_VIEW = "advances.view_all"
_ADVANCES_MUTATE = "advances.process"
_ADVANCES_APPROVE = "advances.approve"
_ADVANCES_REFUSE = "advances.refuse"


def _require_advance_employee_access(
    current_user: User, company_id: str, permission_code: str, employee_id: str
) -> None:
    access_control_service.require_employee_access(
        current_user, company_id, permission_code, employee_id
    )


def _filter_company_rows_in_scope(
    current_user: User,
    company_id: str,
    permission_code: str,
    rows: list,
) -> list:
    scoped = [
        row
        for row in rows
        if str(row.get("company_id") or "") == str(company_id)
    ]
    if current_user.is_platform_admin:
        return scoped
    employee_ids = [str(row.get("employee_id") or "") for row in scoped]
    allowed = set(
        access_control_service.filter_allowed_employee_ids(
            str(current_user.id), company_id, permission_code, employee_ids
        )
    )
    if not allowed and current_user.has_rh_access_in_company(company_id):
        return scoped
    return [row for row in scoped if str(row.get("employee_id") or "") in allowed]


def _require_advance_scope(
    current_user: User, company_id: str, advance_id: str, permission_code: str
) -> dict:
    advance = queries.get_salary_advance(advance_id)
    if str(advance.get("company_id") or "") != str(company_id):
        raise HTTPException(status_code=404, detail="Avance non trouvée.")
    _require_advance_employee_access(
        current_user,
        company_id,
        permission_code,
        str(advance.get("employee_id") or ""),
    )
    return advance


def _require_seizure_scope(
    current_user: User, company_id: str, seizure_id: str, permission_code: str
) -> dict:
    seizure = queries.get_salary_seizure(seizure_id)
    if str(seizure.get("company_id") or "") != str(company_id):
        raise HTTPException(status_code=404, detail="Saisie non trouvée.")
    _require_advance_employee_access(
        current_user,
        company_id,
        permission_code,
        str(seizure.get("employee_id") or ""),
    )
    return seizure


def _require_payslip_scope(
    current_user: User, payslip_id: str, permission_code: str
) -> None:
    from app.modules.payslips.application.router_queries import get_payslip_meta_for_access

    meta = get_payslip_meta_for_access(payslip_id)
    if not meta:
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    company_id = str(meta.get("company_id") or "")
    employee_id = str(meta.get("employee_id") or "")
    if company_id != _active_company_id(current_user):
        raise HTTPException(status_code=404, detail="Bulletin introuvable")
    _require_advance_employee_access(
        current_user, company_id, permission_code, employee_id
    )


def _require_payment_scope(
    current_user: User, company_id: str, payment_id: str, permission_code: str
) -> None:
    payment = queries.get_payment_with_advance(payment_id)
    if not payment:
        raise HTTPException(status_code=404, detail="Paiement non trouvé.")
    advance = payment.get("salary_advances") or payment.get("advance") or {}
    if str(advance.get("company_id") or "") != str(company_id):
        raise HTTPException(status_code=404, detail="Paiement non trouvé.")
    _require_advance_employee_access(
        current_user,
        company_id,
        permission_code,
        str(advance.get("employee_id") or ""),
    )


def _handle_error(e: Exception) -> None:
    if isinstance(e, HTTPException):
        raise e
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_employee_access(
            current_user,
            company_id,
            _ADVANCES_MUTATE,
            seizure_data.employee_id,
        )
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        if employee_id:
            _require_advance_employee_access(
                current_user, company_id, _ADVANCES_VIEW, employee_id
            )
        rows = queries.get_salary_seizures(employee_id=employee_id, status=status)
        return _filter_company_rows_in_scope(
            current_user, company_id, _ADVANCES_VIEW, rows
        )
    except Exception as e:
        _handle_error(e)


@router.get("/salary-seizures/{seizure_id}", response_model=SalarySeizure)
async def get_salary_seizure(
    seizure_id: str,
    current_user: User = Depends(get_current_user),
):
    """Récupère les détails d'une saisie."""
    try:
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_seizure_scope(current_user, company_id, seizure_id, _ADVANCES_VIEW)
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_seizure_scope(current_user, company_id, seizure_id, _ADVANCES_MUTATE)
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_seizure_scope(current_user, company_id, seizure_id, _ADVANCES_MUTATE)
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
        return queries.get_my_salary_advances_for_user_account(
            str(current_user.id), current_user.active_company_id
        )
    except Exception as e:
        _handle_error(e)


@router.get(
    "/employees/me/advance-available",
    response_model=AdvanceAvailableAmount,
)
async def get_my_advance_available(
    advance_type: Optional[
        Literal["avance_salaire", "acompte_salaire", "acompte_prime"]
    ] = Query("avance_salaire"),
    current_user: User = Depends(get_current_user),
):
    """Récupère le montant disponible pour une avance ou un acompte (employé)."""
    try:
        return queries.get_my_advance_available_for_user_account(
            str(current_user.id),
            current_user.active_company_id,
            advance_type=advance_type or "avance_salaire",
        )
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


# ========== SAISIES / AVANCES PAR EMPLOYÉ ==========


@router.get(
    "/employees/{employee_id}/advance-available",
    response_model=AdvanceAvailableAmount,
)
async def get_employee_advance_available(
    employee_id: str,
    year: Optional[int] = Query(None),
    month: Optional[int] = Query(None, ge=1, le=12),
    advance_type: Optional[
        Literal["avance_salaire", "acompte_salaire", "acompte_prime"]
    ] = Query("avance_salaire"),
    current_user: User = Depends(get_current_user),
):
    """Récupère le montant disponible pour une avance ou un acompte (RH / admin)."""
    try:
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_employee_access(
            current_user, company_id, _ADVANCES_VIEW, employee_id
        )
        return queries.get_employee_advance_available(
            employee_id, year, month, advance_type=advance_type or "avance_salaire"
        )
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_employee_access(
            current_user, company_id, _ADVANCES_VIEW, employee_id
        )
        rows = queries.get_employee_salary_seizures(employee_id)
        return _filter_company_rows_in_scope(
            current_user, company_id, _ADVANCES_VIEW, rows
        )
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
        if current_user.is_platform_admin or (
            current_user.active_company_id
            and current_user.has_rh_access_in_company(current_user.active_company_id)
        ):
            company_id = _active_company_id(current_user)
            _require_advance_employee_access(
                current_user,
                company_id,
                _ADVANCES_MUTATE,
                advance_data.employee_id,
            )
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
    advance_type: Optional[
        Literal["avance_salaire", "acompte_salaire", "acompte_prime"]
    ] = Query(None),
    current_user: User = Depends(get_current_user),
):
    """Récupère la liste des avances et acomptes avec filtres."""
    try:
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        if employee_id:
            _require_advance_employee_access(
                current_user, company_id, _ADVANCES_VIEW, employee_id
            )
        rows = queries.get_salary_advances(
            employee_id=employee_id,
            status=status,
            advance_type=advance_type,
        )
        return _filter_company_rows_in_scope(
            current_user, company_id, _ADVANCES_VIEW, rows
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_scope(current_user, company_id, advance_id, _ADVANCES_VIEW)
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_scope(
            current_user, company_id, advance_id, _ADVANCES_APPROVE
        )
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_scope(
            current_user, company_id, advance_id, _ADVANCES_REFUSE
        )
        return commands.reject_salary_advance(
            advance_id,
            rejection_data.rejection_reason,
        )
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)


@router.patch(
    "/salary-advances/{advance_id}/reconcile-prime",
    response_model=SalaryAdvance,
)
async def reconcile_acompte_prime_endpoint(
    advance_id: str,
    reconcile_data: AcomptePrimeReconcile,
    current_user: User = Depends(get_current_user),
):
    """Réconcilie un acompte sur prime avec le montant définitif (RH)."""
    try:
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_scope(
            current_user, company_id, advance_id, _ADVANCES_MUTATE
        )
        return commands.reconcile_acompte_prime(advance_id, reconcile_data)
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_employee_access(
            current_user, company_id, _ADVANCES_VIEW, employee_id
        )
        rows = queries.get_employee_salary_advances(employee_id)
        return _filter_company_rows_in_scope(
            current_user, company_id, _ADVANCES_VIEW, rows
        )
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
        _require_rh_or_admin(current_user)
        _require_payslip_scope(current_user, payslip_id, _ADVANCES_VIEW)
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
        _require_rh_or_admin(current_user)
        _require_payslip_scope(current_user, payslip_id, _ADVANCES_VIEW)
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
        _require_rh_or_admin(current_user)
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_scope(
            current_user, company_id, payment_data.advance_id, _ADVANCES_MUTATE
        )
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_advance_scope(
            current_user, company_id, advance_id, _ADVANCES_VIEW
        )
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_payment_scope(
            current_user, company_id, payment_id, _ADVANCES_VIEW
        )
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
        _require_rh_or_admin(current_user)
        company_id = _active_company_id(current_user)
        _require_payment_scope(
            current_user, company_id, payment_id, _ADVANCES_MUTATE
        )
        return commands.delete_advance_payment(payment_id)
    except SaisiesAvancesError as e:
        _handle_error(e)
    except Exception as e:
        _handle_error(e)
