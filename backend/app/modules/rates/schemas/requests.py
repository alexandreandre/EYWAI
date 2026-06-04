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


class ManualRateUpdateRequest(BaseModel):
    """Saisie manuelle d'un bloc de configuration de taux (admin plateforme)."""

    config_key: str = Field(
        ...,
        min_length=1,
        description="Clé payroll_config à versionner (smic, pss, cotisations, …)",
    )
    config_data: dict = Field(
        ...,
        description="Nouveau contenu complet de config_data pour ce config_key",
    )
    comment: str | None = Field(
        default=None,
        max_length=500,
        description="Note libre justifiant la saisie manuelle",
    )
    source_links: list[str] | None = Field(
        default=None,
        description="Liens de référence éventuels (sources officielles)",
    )
