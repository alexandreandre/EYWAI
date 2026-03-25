"""
Schémas Pydantic sortie API du module companies.

Définitions canoniques : détails + KPIs, settings.
Contrat identique à l'existant (GET/PATCH /api/company/details, /settings).
"""

from typing import Any, Dict

from pydantic import BaseModel, Field


# ----- GET /api/company/settings et PATCH /api/company/settings -----


class CompanySettingsResponse(BaseModel):
    """Réponse GET /settings et PATCH /settings."""

    medical_follow_up_enabled: bool = Field(
        ..., description="Module suivi médical activé"
    )
    settings: Dict[str, Any] = Field(
        default_factory=dict, description="Objet settings complet"
    )


# ----- GET /api/company/details -----


class CompanyDetailsResponse(BaseModel):
    """
    Réponse GET /details.
    company_data = ligne table companies (tous champs).
    kpis = indicateurs (total_employees, last_month_*, evolution_12_months, etc.).
    """

    company_data: Dict[str, Any] = Field(
        ..., description="Données entreprise (table companies)"
    )
    kpis: Dict[str, Any] = Field(
        ...,
        description=(
            "Indicateurs : total_employees, last_month_gross_salary, "
            "evolution_12_months, contract_distribution, job_distribution, etc."
        ),
    )
