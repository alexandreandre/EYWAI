"""Dépendances d'authentification et d'autorisation HTTP du Copilot."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User


def require_copilot_rh_user(
    current_user: User = Depends(get_current_user),
    x_active_company: Annotated[
        str | None, Header(alias="X-Active-Company")
    ] = None,
) -> User:
    """Exige un accès RH à l'entreprise active."""
    company_id = current_user.active_company_id
    if (
        not x_active_company
        or x_active_company != company_id
        or not company_id
        or not current_user.has_access_to_company(company_id)
    ):
        raise HTTPException(
            status_code=403,
            detail="Entreprise active non autorisée.",
        )
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Accès réservé aux profils RH.",
        )
    return current_user
