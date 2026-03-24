"""
Dépendances FastAPI du module promotions.

Contexte utilisateur et garde-fous d'autorisation (RH, admin).
Aucune logique métier : uniquement extraction company_id et vérifications d'accès.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User


def get_company_id_required(current_user: User = Depends(get_current_user)) -> str:
    """Retourne le company_id actif ; lève 400 si aucun."""
    cid = current_user.active_company_id
    if not cid:
        raise HTTPException(
            status_code=400,
            detail="Aucune entreprise active sélectionnée.",
        )
    return str(cid)


def require_rh(current_user: User = Depends(get_current_user)) -> User:
    """Vérifie que l'utilisateur a les droits RH ; lève 403 sinon. Retourne l'utilisateur."""
    if getattr(current_user, "is_super_admin", False):
        return current_user
    if not current_user.active_company_id:
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    if not current_user.has_rh_access_in_company(current_user.active_company_id):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    return current_user


def require_rh_and_company(
    current_user: User = Depends(require_rh),
    company_id: str = Depends(get_company_id_required),
) -> tuple[User, str]:
    """Combine require_rh et company_id pour les routes qui en ont besoin."""
    return current_user, company_id


def can_approve_reject(user: User, company_id: str) -> bool:
    """Indique si l'utilisateur peut approuver/rejeter une promotion (admin ou super_admin)."""
    if getattr(user, "is_super_admin", False):
        return True
    return user.is_admin_in_company(company_id)


__all__ = [
    "get_current_user",
    "get_company_id_required",
    "require_rh",
    "require_rh_and_company",
    "can_approve_reject",
]
