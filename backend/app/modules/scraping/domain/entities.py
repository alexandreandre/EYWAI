"""
Entités du domaine scraping.

Représentations métier alignées sur les tables scraping_sources, scraping_jobs,
scraping_schedules, scraping_alerts. Pour l'instant placeholders ; la migration
remplira depuis l'infrastructure (dict Supabase) via des mappers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class ScrapingSource:
    """Source de données à scraper (catalogue)."""

    id: str
    source_key: str
    source_name: str
    source_type: str
    is_active: bool
    is_critical: bool
    orchestrator_path: Optional[str] = None
    available_scrapers: Optional[List[str]] = None
    # Champs optionnels pour enrichissement
    raw: Optional[Dict[str, Any]] = None


@dataclass
class ScrapingJob:
    """Job d'exécution d'un scraper."""

    id: str
    source_id: str
    job_type: str
    status: str
    success: Optional[bool] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None


@dataclass
class ScrapingSchedule:
    """Planification d'exécution automatique."""

    id: str
    source_id: str
    schedule_type: str
    is_enabled: bool
    raw: Optional[Dict[str, Any]] = None


@dataclass
class ScrapingAlert:
    """Alerte liée à un job ou une source."""

    id: str
    alert_type: str
    severity: str
    job_id: Optional[str] = None
    source_id: Optional[str] = None
    is_read: bool = False
    is_resolved: bool = False
    raw: Optional[Dict[str, Any]] = None
