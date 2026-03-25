"""
Mappers dict/BDD <-> DTOs du module saisies_avances.

Construction des schémas de réponse (AdvanceAvailableAmount, SeizableAmountCalculation)
à partir des données brutes ou des sorties des règles.
"""

from decimal import Decimal
from typing import Any, Dict

from app.modules.saisies_avances.schemas import (
    AdvanceAvailableAmount,
    SeizableAmountCalculation,
)


def to_advance_available_amount(data: Dict[str, Any]) -> AdvanceAvailableAmount:
    """Construit AdvanceAvailableAmount depuis le dict de build_advance_available."""
    return AdvanceAvailableAmount(
        daily_salary=data["daily_salary"],
        days_worked=data["days_worked"],
        outstanding_advances=data["outstanding_advances"],
        available_amount=data["available_amount"],
        max_advance_days=data.get("max_advance_days", 10),
    )


def to_seizable_amount_calculation(
    net_salary: Decimal,
    dependents_count: int,
    adjusted_salary: Decimal,
    seizable_amount: Decimal,
    minimum_untouchable: Decimal,
) -> SeizableAmountCalculation:
    """Construit SeizableAmountCalculation depuis les valeurs calculées."""
    return SeizableAmountCalculation(
        net_salary=net_salary,
        dependents_count=dependents_count,
        adjusted_salary=adjusted_salary,
        seizable_amount=seizable_amount,
        minimum_untouchable=minimum_untouchable,
    )
