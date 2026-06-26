"""
Schémas Pydantic sortie API du module companies.

Définitions canoniques : détails + KPIs, settings.
Contrat identique à l'existant (GET/PATCH /api/company/details, /settings).
"""

from typing import Any, Dict, List, Optional

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


class CompanyOverviewResponse(BaseModel):
    """Réponse GET /overview : indicateurs RH consolidés."""

    demographics: Dict[str, Any] = Field(default_factory=dict)
    movements: Dict[str, Any] = Field(default_factory=dict)
    absenteeism: Dict[str, Any] = Field(default_factory=dict)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)
    compliance: Dict[str, Any] = Field(default_factory=dict)
    cdd_ending_within_30_days: int = Field(0, description="Nombre de CDD finissant sous 30j")
    dsn_coverage: Optional[Dict[str, Any]] = Field(
        None,
        description="Couverture import DSN (mois couverts, statut, timeline)",
    )
