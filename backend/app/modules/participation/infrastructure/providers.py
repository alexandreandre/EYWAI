"""
Providers du module participation.

Implémentation des ports du domain : données employés pour le simulateur.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.modules.participation.domain.interfaces import (
    IEmployeeParticipationDataProvider,
)
from app.modules.participation.infrastructure.queries import (
    fetch_employee_participation_data,
)


class EmployeeParticipationDataProvider(IEmployeeParticipationDataProvider):
    """
    Fournit les données employés pour le simulateur (salaire annuel, présence, ancienneté).
    Délègue à fetch_employee_participation_data (queries + domain rules).
    """

    def get_employee_participation_data(
        self,
        company_id: str,
        year: int,
    ) -> List[Dict[str, Any]]:
        """Liste de dicts : employee_id, first_name, last_name, annual_salary, presence_days, seniority_years, has_real_salary, has_real_presence."""
        return fetch_employee_participation_data(company_id, year)


def get_employee_participation_data_provider() -> IEmployeeParticipationDataProvider:
    """Factory : retourne le provider par défaut."""
    return EmployeeParticipationDataProvider()
