"""
Schémas de réponse pour le module rates.

- RateCategory : contrat GET /api/rates/all (frontend Rates.tsx).
- ContributionRate, DashboardRatesResponse : définis ici (réexportés par schemas/general.py pour compatibilité).
À conserver strictement pour compatibilité.
"""

from __future__ import annotations

from typing import Any, List

from pydantic import BaseModel, Field


class ContributionRate(BaseModel):
    """Taux de cotisation (ex. pour dashboard / synthèse)."""

    id: str
    libelle: str
    salarial: float | dict | str | None = None
    patronal: float | dict | str | None = None
    status: str


class DashboardRatesResponse(BaseModel):
    """Réponse agrégée des taux pour le dashboard."""

    rates: List[ContributionRate]
    last_check: str | None = None


class RateCategory(BaseModel):
    """Une catégorie de taux (config_key) avec métadonnées."""

    config_data: Any = Field(
        ...,
        description="Données de configuration (structure variable selon config_key)",
    )
    version: int | None = Field(None, description="Version de la configuration")
    last_checked_at: str | None = Field(
        None, description="Date du dernier contrôle (ISO)"
    )
    comment: str | None = Field(None, description="Commentaire optionnel")
    source_links: list[str] | None = Field(
        None, description="Liens sources (ex. LegiSocial)"
    )

    model_config = {"extra": "forbid"}


# Réponse GET /api/rates/all : dict[config_key, RateCategory]
# On ne définit pas de modèle Pydantic pour le dict entier pour garder
# la compatibilité exacte avec le JSON retourné (clés dynamiques).
# Le routeur peut retourner dict[str, dict] mappé depuis RateCategory.model_dump().
