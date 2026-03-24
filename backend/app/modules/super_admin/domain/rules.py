"""
Règles métier du domaine super_admin.

Règles pures sur l'entité SuperAdmin. Pas de FastAPI, pas d'I/O.
"""
from __future__ import annotations

from app.modules.super_admin.domain.entities import SuperAdmin
from app.modules.super_admin.domain.exceptions import SuperAdminPermissionDenied


def require_can_create_companies(super_admin: SuperAdmin) -> None:
    """
    Lève SuperAdminPermissionDenied si le super admin n'a pas la permission de créer des entreprises.
    À appeler avant create_company.
    """
    if not super_admin.can_create_companies:
        raise SuperAdminPermissionDenied("Vous n'avez pas la permission de créer des entreprises")


def require_can_delete_companies(super_admin: SuperAdmin) -> None:
    """
    Lève SuperAdminPermissionDenied si le super admin n'a pas la permission de supprimer des entreprises.
    À appeler avant delete_company_permanent.
    """
    if not super_admin.can_delete_companies:
        raise SuperAdminPermissionDenied("Vous n'avez pas la permission de supprimer des entreprises")
