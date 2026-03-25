"""
Requêtes applicatives (read) pour bonus_types.

Délèguent au BonusTypesService ; logique métier dans le service.
"""

from __future__ import annotations

from app.modules.bonus_types.application.dto import BonusCalculationResult
from app.modules.bonus_types.application.service import (
    BonusTypesService,
    get_bonus_types_service,
)
from app.modules.bonus_types.domain.entities import BonusType


def list_bonus_types_by_company(
    company_id: str,
    service: BonusTypesService | None = None,
) -> list[BonusType]:
    """Liste les primes du catalogue pour une entreprise (ordre libelle)."""
    svc = service or get_bonus_types_service()
    return svc.list_by_company(company_id)


def get_bonus_type_by_id(
    bonus_type_id: str,
    company_id: str | None = None,
    service: BonusTypesService | None = None,
) -> BonusType | None:
    """Retourne une prime par id ; si company_id fourni, filtre sur l'entreprise."""
    svc = service or get_bonus_types_service()
    return svc.get_by_id(bonus_type_id, company_id)


def calculate_bonus_amount(
    bonus_type_id: str,
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    service: BonusTypesService | None = None,
) -> BonusCalculationResult:
    """Calcule le montant d'une prime (montant_fixe ou selon_heures)."""
    svc = service or get_bonus_types_service()
    return svc.calculate_amount(bonus_type_id, company_id, employee_id, year, month)
