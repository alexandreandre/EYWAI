"""
Exceptions du domaine super_admin.

Règles métier pures : pas de dépendance FastAPI/HTTP.
"""

from __future__ import annotations


class SuperAdminPermissionDenied(Exception):
    """Levée lorsqu'un super admin n'a pas la permission requise (ex. can_create_companies, can_delete_companies)."""

    pass
