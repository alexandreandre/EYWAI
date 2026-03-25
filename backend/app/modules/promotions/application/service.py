"""
Orchestration partagée du module promotions.

Délègue à l'infrastructure (IEmployeeUpdater). Aucune logique DB ici.
"""

from __future__ import annotations

from app.modules.promotions.domain.enums import RhAccessRole
from app.modules.promotions.domain.interfaces import PromotionApplyProtocol
from app.modules.promotions.infrastructure.providers import get_employee_updater


def apply_promotion_changes(
    promotion: PromotionApplyProtocol,
    company_id: str,
) -> None:
    """Applique les changements d'une promotion à l'employé et aux accès RH (délègue à l'infra)."""
    get_employee_updater().apply_promotion_changes(promotion, company_id)


def update_employee_rh_access(
    employee_id: str,
    company_id: str,
    new_rh_access: RhAccessRole,
    promotion_id: str,
) -> None:
    """Met à jour les accès RH d'un employé (délègue à l'infra)."""
    get_employee_updater().update_employee_rh_access(
        employee_id=employee_id,
        company_id=company_id,
        new_rh_access=new_rh_access,
        promotion_id=promotion_id,
    )


__all__ = ["apply_promotion_changes", "update_employee_rh_access"]
