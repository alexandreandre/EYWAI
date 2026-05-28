"""Schémas de requête pour le module rates."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RatesSyncRequest(BaseModel):
    """Cible de mise à jour (au moins un filtre, ou vide = toutes les sources critiques)."""

    rate_keys: list[str] | None = Field(
        default=None,
        description="Clés payroll_config (smic, pss, cotisations, …)",
    )
    source_keys: list[str] | None = Field(
        default=None,
        description="Clés scraping_sources (SMIC, CSG, AGIRC-ARRCO, …)",
    )
    cotisation_ids: list[str] | None = Field(
        default=None,
        description="Identifiants de lignes dans config_data.cotisations",
    )
