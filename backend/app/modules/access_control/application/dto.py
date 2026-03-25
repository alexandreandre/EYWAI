"""
DTOs pour le module access_control.

Résultats des vérifications d'autorisation (pour réponses API ou usage interne) :
- PermissionCheckResult, RoleHierarchyCheckResult : utilisés par queries (check_permission, check_hierarchy).

Les cas d'usage listes / matrice / templates retournent directement les schémas
schemas.permissions (PermissionCategory, PermissionMatrix, UserPermissionsSummary, etc.)
pour conserver le comportement exact des routers legacy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PermissionCheckResult:
    """Résultat d'une vérification de permission."""

    has_permission: bool
    permission_code: str
    user_id: str
    company_id: str


@dataclass
class RoleHierarchyCheckResult:
    """Résultat d'une vérification hiérarchie (création/modification de rôle)."""

    is_allowed: bool
    creator_role: str
    target_role: str
    company_id: str
