"""
DTOs applicatifs du module scraping.

Objets de transfert entre api et application / application et infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ScrapingDashboardResult:
    """Résultat agrégé pour GET /dashboard."""

    stats: Dict[str, Any]
    recent_jobs: List[Dict[str, Any]]
    unread_alerts: List[Dict[str, Any]]
    critical_sources: List[Dict[str, Any]]


@dataclass
class ExecuteScraperResult:
    """Résultat de l'exécution d'un scraper (synchrone ou async)."""

    job_id: str
    success: Optional[bool] = None
    duration_ms: Optional[int] = None
    error_message: Optional[str] = None
    data_extracted: Optional[Dict[str, Any]] = None
    message: Optional[str] = None  # ex: "Scraping lancé en arrière-plan"
