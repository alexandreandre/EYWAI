"""
Service applicatif du module super_admin.

Vérification super admin (repository + mapper) et helpers de permission (domain rules).
Pas de FastAPI ; exceptions pour mapping HTTP côté router.
"""
from __future__ import annotations

from typing import Any, Dict

from app.modules.super_admin.domain.exceptions import SuperAdminPermissionDenied
from app.modules.super_admin.domain import rules as domain_rules
from app.modules.super_admin.infrastructure.mappers import row_to_super_admin, super_admin_to_row
from app.modules.super_admin.infrastructure.repository import get_by_user_id


class SuperAdminAccessError(Exception):
    """Levée lorsque l'utilisateur connecté n'est pas super admin ou n'a pas la permission requise."""
    pass


def verify_super_admin_and_return_row(current_user_id: str) -> Dict[str, Any]:
    """
    Vérifie que l'utilisateur connecté est un super admin actif et retourne la ligne super_admins (dict).
    Lève SuperAdminAccessError si non super admin (mapping 403 côté router).
    """
    entity = get_by_user_id(current_user_id)
    if entity is None:
        raise SuperAdminAccessError("Accès refusé : vous devez être super administrateur")
    return super_admin_to_row(entity)


def require_can_create_companies(super_admin_row: Dict[str, Any]) -> None:
    """Lève SuperAdminAccessError si le super admin n'a pas la permission de créer des entreprises."""
    try:
        super_admin = row_to_super_admin(super_admin_row)
        domain_rules.require_can_create_companies(super_admin)
    except SuperAdminPermissionDenied as e:
        raise SuperAdminAccessError(str(e)) from e


def require_can_delete_companies(super_admin_row: Dict[str, Any]) -> None:
    """Lève SuperAdminAccessError si le super admin n'a pas la permission de supprimer des entreprises."""
    try:
        super_admin = row_to_super_admin(super_admin_row)
        domain_rules.require_can_delete_companies(super_admin)
    except SuperAdminPermissionDenied as e:
        raise SuperAdminAccessError(str(e)) from e
