"""
Value objects du domaine super_admin.

Préparation migration : permissions et données dérivées.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuperAdminPermissions:
    """Permissions d'un super admin (can_create_companies, can_delete_companies, etc.)."""

    can_create_companies: bool
    can_delete_companies: bool
    can_view_all_data: bool
    can_impersonate: bool
