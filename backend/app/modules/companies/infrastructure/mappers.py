"""
Mappers DB <-> domain / DTOs.

row companies -> Company ; raw settings -> CompanySettingsResultDto.
"""
from typing import Any, Dict

from app.modules.companies.domain.entities import Company
from app.modules.companies.application.dto import CompanySettingsResultDto


def row_to_company(row: Dict[str, Any]) -> Company:
    """Ligne table companies -> entité Company."""
    return Company(
        id=str(row["id"]),
        company_name=row.get("company_name", ""),
        siret=row.get("siret"),
        settings=row.get("settings"),
        is_active=row.get("is_active", True),
    )


def settings_to_dto(settings: Dict[str, Any]) -> CompanySettingsResultDto:
    """Colonne settings -> DTO réponse API."""
    return CompanySettingsResultDto(
        medical_follow_up_enabled=bool(settings.get("medical_follow_up_enabled")),
        settings=dict(settings),
    )
