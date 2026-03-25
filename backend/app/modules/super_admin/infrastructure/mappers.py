"""
Mappers DB <-> domaine du module super_admin.

Préparation migration : row super_admins -> SuperAdmin.
"""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from app.modules.super_admin.domain.entities import SuperAdmin


def row_to_super_admin(row: Dict[str, Any]) -> SuperAdmin:
    """
    Convertit une ligne table super_admins en entité SuperAdmin.
    Champs : id, user_id, email, first_name, last_name, can_create_companies,
    can_delete_companies, can_view_all_data, can_impersonate, is_active, created_at, last_login_at, notes.
    """
    return SuperAdmin(
        id=UUID(row["id"]) if isinstance(row["id"], str) else row["id"],
        user_id=UUID(row["user_id"])
        if isinstance(row["user_id"], str)
        else row["user_id"],
        email=row["email"],
        first_name=row["first_name"],
        last_name=row["last_name"],
        can_create_companies=row.get("can_create_companies", True),
        can_delete_companies=row.get("can_delete_companies", False),
        can_view_all_data=row.get("can_view_all_data", True),
        can_impersonate=row.get("can_impersonate", False),
        is_active=row.get("is_active", True),
        created_at=row.get("created_at"),
        last_login_at=row.get("last_login_at"),
        notes=row.get("notes"),
    )


def super_admin_to_row(entity: SuperAdmin) -> Dict[str, Any]:
    """Convertit une entité SuperAdmin en dict pour écriture DB. Placeholder si besoin."""
    return {
        "id": str(entity.id),
        "user_id": str(entity.user_id),
        "email": entity.email,
        "first_name": entity.first_name,
        "last_name": entity.last_name,
        "can_create_companies": entity.can_create_companies,
        "can_delete_companies": entity.can_delete_companies,
        "can_view_all_data": entity.can_view_all_data,
        "can_impersonate": entity.can_impersonate,
        "is_active": entity.is_active,
        "created_at": entity.created_at,
        "last_login_at": entity.last_login_at,
        "notes": entity.notes,
    }
