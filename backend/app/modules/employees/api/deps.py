"""Helpers HTTP partagés pour les routers employees."""

from __future__ import annotations

from fastapi import HTTPException

from app.core.platform_admin import is_platform_admin
from app.modules.users.schemas.responses import User
from app.shared.employee_resolution import resolve_employee_id_for_user_account


def assert_can_read_employee_profile(
    current_user: User, employee_id: str, company_id: str
) -> None:
    """RH : toute fiche de la société ; collaborateur : uniquement la sienne."""
    if not current_user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise.",
        )
    if is_platform_admin(current_user) or current_user.has_rh_access_in_company(
        company_id
    ):
        return
    allowed = {str(current_user.id)}
    scoped = resolve_employee_id_for_user_account(
        str(current_user.id), str(company_id)
    )
    if scoped:
        allowed.add(str(scoped))
    if str(employee_id) not in allowed:
        raise HTTPException(status_code=403, detail="Accès non autorisé.")


def resolve_my_employee_id(current_user: User) -> str:
    """employees.id pour les routes /me/* (compte auth ≠ fiche si user_id renseigné)."""
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Impossible de déterminer l'entreprise.",
        )
    employee_id = resolve_employee_id_for_user_account(
        str(current_user.id), str(company_id)
    )
    if not employee_id:
        raise HTTPException(status_code=404, detail="Employé non trouvé.")
    return employee_id


def require_rh_access(company_id: str | None, current_user: User) -> str:
    """Entreprise active, accès entreprise et profil RH."""
    if not company_id:
        raise HTTPException(
            status_code=403,
            detail="Impossible de déterminer l'entreprise.",
        )
    if not current_user.has_access_to_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès non autorisé pour cette entreprise.",
        )
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")
    return company_id
