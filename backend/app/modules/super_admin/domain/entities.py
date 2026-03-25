"""
Entités du domaine super_admin.

Préparation migration : structure alignée sur la table super_admins
(api/routers/super_admin.py, migrations/00_create_super_admin.sql).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass(frozen=False)
class SuperAdmin:
    """
    Super administrateur plateforme.
    Correspond à une ligne de la table super_admins.
    """

    id: UUID
    user_id: UUID
    email: str
    first_name: str
    last_name: str
    can_create_companies: bool
    can_delete_companies: bool
    can_view_all_data: bool
    can_impersonate: bool
    is_active: bool
    created_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None
    notes: Optional[str] = None
