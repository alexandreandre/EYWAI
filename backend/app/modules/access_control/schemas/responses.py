"""
Schémas de réponse pour les endpoints du module access_control.

Définitions canoniques (ex-migration depuis schemas.permissions).
Comportement identique : types et champs inchangés.
"""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class PermissionCheckResponse(BaseModel):
    """Réponse pour la vérification d'une permission."""
    has_permission: bool
    permission_code: str
    user_id: UUID
    company_id: UUID


class RoleHierarchyCheckResponse(BaseModel):
    """Réponse pour la vérification de la hiérarchie."""
    is_allowed: bool
    creator_role: str
    target_role: str
    message: str
