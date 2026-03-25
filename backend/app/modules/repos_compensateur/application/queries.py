"""
Queries (cas d'usage lecture) pour repos_compensateur.

Délèguent à l'infrastructure (repository). Comportement identique.
"""

from __future__ import annotations

from app.modules.repos_compensateur.infrastructure import get_jours_by_employee_year


def get_credits_jours_by_employee_year(
    employee_ids: list[str], year: int
) -> dict[str, float]:
    """
    Somme des jours repos_compensateur_credits par employee_id pour l'année.
    Utilisable par le module absences pour les soldes (acquired repos compensateur).
    """
    return get_jours_by_employee_year(employee_ids, year)
