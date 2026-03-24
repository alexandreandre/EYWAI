"""
Commandes applicatives (write) pour bonus_types.

Délèguent au BonusTypesService ; logique métier dans le service.
"""
from __future__ import annotations

from app.modules.bonus_types.application.dto import (
    BonusTypeCreateInput,
    BonusTypeUpdateInput,
)
from app.modules.bonus_types.application.service import (
    BonusTypesService,
    get_bonus_types_service,
)
from app.modules.bonus_types.domain.entities import BonusType


def create_bonus_type(
    input_data: BonusTypeCreateInput,
    has_rh_access: bool,
    service: BonusTypesService | None = None,
) -> BonusType:
    """Crée une prime dans le catalogue. Vérifications (company, RH) dans le service."""
    svc = service or get_bonus_types_service()
    return svc.create(input_data, has_rh_access)


def update_bonus_type(
    bonus_type_id: str,
    company_id: str,
    has_rh_access: bool,
    input_data: BonusTypeUpdateInput,
    service: BonusTypesService | None = None,
) -> BonusType | None:
    """Met à jour une prime. Vérifications (ownership, RH) dans le service."""
    svc = service or get_bonus_types_service()
    return svc.update(bonus_type_id, company_id, has_rh_access, input_data)


def delete_bonus_type(
    bonus_type_id: str,
    company_id: str,
    is_super_admin: bool,
    has_rh_access: bool,
    service: BonusTypesService | None = None,
) -> bool:
    """Supprime une prime. Vérifications (ownership, super_admin ou RH) dans le service."""
    svc = service or get_bonus_types_service()
    return svc.delete(bonus_type_id, company_id, is_super_admin, has_rh_access)
