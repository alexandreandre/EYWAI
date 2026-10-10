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


def list_monthly_inputs_by_period(
    year: int, month: int, company_id: str
) -> ListMonthlyInputsResultDto:
    """Saisies du mois pour LA SOCIÉTÉ de l'appelant. Ordre created_at desc."""
    items = monthly_inputs_repository.list_by_period(year, month, company_id)
    return ListMonthlyInputsResultDto(items=items)


def list_monthly_inputs_by_employee_period(
    employee_id: str, year: int, month: int, company_id: str
) -> ListMonthlyInputsResultDto:
    """Saisies d'un salarié pour un mois, dans la société de l'appelant."""
    items = monthly_inputs_repository.list_by_employee_period(
        employee_id, year, month, company_id
    )
    return ListMonthlyInputsResultDto(items=items)


def get_primes_catalogue() -> list:
    """Retourne le catalogue de primes (payroll_config, config_key=primes). Délégation au provider."""
    return primes_catalogue_provider.get_primes_catalogue()


def bulletins_a_recalculer(
    company_id: str, cibles: list[tuple[str, int, int]]
) -> list[dict]:
    """Parmi (salarié, année, mois), ceux dont le bulletin existe déjà : une saisie
    qui change les rend « À recalculer ». Liste vide si aucun bulletin."""
    par_mois: dict[tuple[int, int], list[str]] = {}
    for employee_id, year, month in cibles:
        ids = par_mois.setdefault((int(year), int(month)), [])
        if str(employee_id) not in ids:
            ids.append(str(employee_id))
    trouves: list[dict] = []
    for (year, month), ids in par_mois.items():
        for employee_id in monthly_inputs_repository.employes_avec_bulletin(
            company_id, year, month, ids
        ):
            trouves.append({"employee_id": employee_id, "year": year, "month": month})
    return trouves


def cible_de_la_saisie(input_id: str, company_id: str) -> tuple[str, int, int] | None:
    """(salarié, année, mois) d'une saisie de la société, None si elle n'existe pas."""
    ligne = monthly_inputs_repository.get_by_id(input_id, company_id)
    if not ligne:
        return None
    return (str(ligne["employee_id"]), int(ligne["year"]), int(ligne["month"]))
