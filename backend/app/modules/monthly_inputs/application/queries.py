"""
Requêtes (cas d'usage lecture) du module monthly_inputs.

Délégation à l'infrastructure (repository, provider catalogue). Pas de DB ni parsing ici.
Comportement identique à api/routers/monthly_inputs.py.
"""

from __future__ import annotations

from app.modules.monthly_inputs.application.dto import ListMonthlyInputsResultDto
from app.modules.monthly_inputs.infrastructure.queries import primes_catalogue_provider
from app.modules.monthly_inputs.infrastructure.repository import (
    monthly_inputs_repository,
)


def list_monthly_inputs_by_period(year: int, month: int) -> ListMonthlyInputsResultDto:
    """Liste toutes les saisies du mois (tous salariés). Ordre created_at desc."""
    items = monthly_inputs_repository.list_by_period(year, month)
    return ListMonthlyInputsResultDto(items=items)


def list_monthly_inputs_by_employee_period(
    employee_id: str, year: int, month: int
) -> ListMonthlyInputsResultDto:
    """Liste les saisies d'un employé pour un mois donné."""
    items = monthly_inputs_repository.list_by_employee_period(employee_id, year, month)
    return ListMonthlyInputsResultDto(items=items)


def get_primes_catalogue() -> list:
    """Retourne le catalogue de primes (payroll_config, config_key=primes). Délégation au provider."""
    return primes_catalogue_provider.get_primes_catalogue()
