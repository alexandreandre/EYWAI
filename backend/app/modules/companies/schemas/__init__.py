"""Schémas API du module companies (requêtes et réponses)."""

from app.modules.companies.schemas.requests import (
    CompanyCreate,
    CompanyCreateWithAdmin,
    CompanySettingsUpdate,
    CompanyUpdate,
)
from app.modules.companies.schemas.responses import (
    CompanyDetailsResponse,
    CompanySettingsResponse,
)

__all__ = [
    "CompanyCreate",
    "CompanyCreateWithAdmin",
    "CompanyDetailsResponse",
    "CompanySettingsResponse",
    "CompanySettingsUpdate",
    "CompanyUpdate",
]
