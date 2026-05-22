"""
Requêtes (cas d'usage lecture) du module companies.

Délégation à l'infrastructure (repository, queries) et au service (calcul KPIs).
Comportement identique à l'ancien routeur api/routers/company.py.
"""

from __future__ import annotations

from typing import Any

from app.modules.companies.application.dto import (
    CompanyDetailsWithKpisDto,
    CompanyOverviewDto,
    CompanySettingsResultDto,
)
from app.modules.companies.domain.kpis import compute_company_kpis
from app.modules.companies.domain.overview import (
    compute_absenteeism,
    compute_alerts,
    compute_compliance_flags,
    compute_demographics,
    compute_movements,
)
from app.modules.companies.infrastructure.overview_queries import fetch_overview_raw
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


def get_company_overview(company_id: str, current_user: Any) -> CompanyOverviewDto:
    """Indicateurs RH consolidés pour la page Mon Entreprise."""
    company = company_repository.get_by_id(company_id)
    if not company:
        raise LookupError("Entreprise non trouvée.")

    raw = fetch_overview_raw(company_id)
    employees = raw["employees"]
    employee_ids = {str(e["id"]) for e in employees if e.get("id")}

    demographics = compute_demographics(employees)
    movements = compute_movements(employees, raw["exits"])
    absenteeism = compute_absenteeism(raw["absences"], employee_ids)
    alerts = compute_alerts(
        company, employees, raw["mutuelle_employee_ids"]
    )
    compliance = compute_compliance_flags(company, demographics["total_headcount"])
    cdd_ending = next(
        (a.get("count", 0) for a in alerts if a.get("code") == "cdd_ending_soon"),
        0,
    )

    return CompanyOverviewDto(
        demographics=demographics,
        movements=movements,
        absenteeism=absenteeism,
        alerts=alerts,
        compliance=compliance,
        cdd_ending_within_30_days=int(cdd_ending),
    )


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
