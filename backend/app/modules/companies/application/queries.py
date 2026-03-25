"""
Requêtes (cas d'usage lecture) du module companies.

Délégation à l'infrastructure (repository, queries) et au service (calcul KPIs).
Comportement identique à l'ancien routeur api/routers/company.py.
"""

from __future__ import annotations

from typing import Any

from app.modules.companies.application.dto import (
    CompanyDetailsWithKpisDto,
    CompanySettingsResultDto,
)
from app.modules.companies.domain.kpis import compute_company_kpis
from app.modules.companies.infrastructure.queries import (
    fetch_company_with_employees_and_payslips,
)
from app.modules.companies.infrastructure.repository import company_repository


def get_company_details_and_kpis(
    company_id: str, current_user: Any
) -> CompanyDetailsWithKpisDto:
    """
    Détails entreprise + KPIs dashboard.
    company_id doit être résolu côté appelant (ex. via service.resolve_company_id_for_details).
    """
    data = fetch_company_with_employees_and_payslips(company_id)
    company_data = data["company_data"]
    employees = data["employees"]
    payslips = data["payslips"]

    if not company_data:
        raise LookupError("Données de l'entreprise non trouvées.")

    kpis = compute_company_kpis(employees, payslips)
    return CompanyDetailsWithKpisDto(company_data=company_data, kpis=kpis)


def get_company_settings(
    company_id: str, current_user: Any
) -> CompanySettingsResultDto:
    """Retourne les settings de l'entreprise (contexte actif)."""
    settings = company_repository.get_settings(company_id)
    if settings is None:
        raise LookupError("Entreprise non trouvée.")
    return CompanySettingsResultDto(
        medical_follow_up_enabled=bool(settings.get("medical_follow_up_enabled")),
        settings=dict(settings),
    )
