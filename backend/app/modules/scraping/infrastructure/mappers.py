"""
Mappers dict DB <-> entités domaine scraping.

Placeholder : à utiliser lors de la migration si on passe par des entités.
Pour l'instant le module travaille en dict pour compatibilité avec le legacy.
"""
from __future__ import annotations

from typing import Any, Dict

from app.modules.scraping.domain.entities import (
    ScrapingAlert,
    ScrapingJob,
    ScrapingSchedule,
    ScrapingSource,
)


def source_row_to_entity(row: Dict[str, Any]) -> ScrapingSource:
    """Convertit une ligne scraping_sources en entité."""
    raise NotImplementedError("Migration: à implémenter si usage des entités")


def job_row_to_entity(row: Dict[str, Any]) -> ScrapingJob:
    """Convertit une ligne scraping_jobs en entité."""
    raise NotImplementedError("Migration: à implémenter si usage des entités")


def schedule_row_to_entity(row: Dict[str, Any]) -> ScrapingSchedule:
    """Convertit une ligne scraping_schedules en entité."""
    raise NotImplementedError("Migration: à implémenter si usage des entités")


def alert_row_to_entity(row: Dict[str, Any]) -> ScrapingAlert:
    """Convertit une ligne scraping_alerts en entité."""
    raise NotImplementedError("Migration: à implémenter si usage des entités")
