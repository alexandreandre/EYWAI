"""Domaine companies : entités, value objects, interfaces, règles, KPIs."""
from app.modules.companies.domain.entities import Company
from app.modules.companies.domain.interfaces import (
    ICompanyDetailsProvider,
    ICompanyRepository,
)
from app.modules.companies.domain.kpis import compute_company_kpis
from app.modules.companies.domain.value_objects import CompanySettings

__all__ = [
    "Company",
    "CompanySettings",
    "ICompanyDetailsProvider",
    "ICompanyRepository",
    "compute_company_kpis",
]
