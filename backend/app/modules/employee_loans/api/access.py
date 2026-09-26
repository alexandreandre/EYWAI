"""Contrôle d'accès prêts employeur (RH vs salarié propriétaire)."""

from __future__ import annotations

from fastapi import HTTPException

from app.modules.access_control.application.service import access_control_service
from app.modules.employee_loans.application import queries
from app.modules.employee_loans.schemas.responses import EmployeeLoan
from app.modules.users.schemas.responses import User

_ERR_NO_COMPANY = "Aucune entreprise active."
_ERR_EMPLOYEE_PROFILE = "Profil employé introuvable pour ce compte."
_ERR_RH_REQUIRED = "Accès réservé aux RH et administrateurs."
_ERR_LOAN_ACCESS = "Accès refusé à ce prêt."


def require_company_id(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail=_ERR_NO_COMPANY)
    if not user.has_access_to_company(cid):
        raise HTTPException(status_code=403, detail="Accès refusé à cette entreprise.")
    return str(cid)


def require_rh_or_admin(user: User) -> str:
    cid = require_company_id(user)
    if user.is_platform_admin:
        return cid
    if not user.has_rh_access_in_company(cid):
        raise HTTPException(status_code=403, detail=_ERR_RH_REQUIRED)
    return cid


def resolve_my_employee_id(user: User) -> str:
    company_id = require_company_id(user)
    from app.shared.employee_resolution import resolve_employee_id_for_user_account

    employee_id = resolve_employee_id_for_user_account(str(user.id), company_id)
    if not employee_id:
        raise HTTPException(status_code=404, detail=_ERR_EMPLOYEE_PROFILE)
    return str(employee_id)


def user_can_access_loan(user: User, loan: EmployeeLoan) -> bool:
    if user.is_platform_admin:
        return True
    company_id = user.active_company_id
    if (
        company_id
        and str(loan.company_id) == str(company_id)
        and user.has_rh_access_in_company(str(company_id))
    ):
        return True
    try:
        my_employee_id = resolve_my_employee_id(user)
    except HTTPException:
        return False
    return str(loan.employee_id) == my_employee_id


def require_loan_access(user: User, loan_id: str) -> EmployeeLoan:
    try:
        loan = queries.get_loan(loan_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not user_can_access_loan(user, loan):
        raise HTTPException(status_code=403, detail=_ERR_LOAN_ACCESS)
    return loan


def require_rh_loan_access(user: User, loan_id: str) -> EmployeeLoan:
    """Mutations d'un prêt : RH de la société active, prêt de cette société.

    Le contrôle de rôle seul ne suffisait pas : le dépôt ne filtre que sur
    l'identifiant du prêt, et une RH de la société A modifiait, annulait ou
    soldait le prêt d'un salarié de la société B (audit du 25/09/2026, E1).
    Même refus que la lecture : 404 si le prêt n'existe pas, 403 sinon.
    """
    require_rh_or_admin(user)
    return require_loan_access(user, loan_id)


def require_rh_employee_in_company(user: User, employee_id: str) -> str:
    """Lecture RH par salarié : le salarié doit appartenir à la société active.

    404 hors société, comme `require_employee_access` : on ne révèle pas
    l'existence du salarié. L'administrateur plateforme garde son accès
    transverse.
    """
    company_id = require_rh_or_admin(user)
    if not user.is_platform_admin:
        access_control_service.assert_employee_in_company(company_id, employee_id)
    return company_id
