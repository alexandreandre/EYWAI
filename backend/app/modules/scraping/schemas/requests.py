"""
Schémas requête API du module scraping.

Définitions canoniques (migration depuis api/routers/scraping.py).
Comportement identique : mêmes champs, mêmes types, mêmes valeurs par défaut.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class ScraperExecutionRequest(BaseModel):
    source_key: str
    scraper_name: Optional[str] = None  # Si None, utilise l'orchestrateur
    use_orchestrator: bool = True  # Force utilisation de l'orchestrateur si disponible


class ScheduleCreate(BaseModel):
    source_id: str
    schedule_type: str  # "cron" ou "interval"
    cron_expression: Optional[str] = None
    interval_days: Optional[int] = None
    notify_on_success: bool = False
    notify_on_failure: bool = True
    notification_emails: List[str] = []


class ScheduleUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    interval_days: Optional[int] = None
    notify_on_success: Optional[bool] = None
    notify_on_failure: Optional[bool] = None
    notification_emails: Optional[List[str]] = None


class AlertResolve(BaseModel):
    resolution_note: Optional[str] = None
