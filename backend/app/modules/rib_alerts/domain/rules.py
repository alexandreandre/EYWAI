"""
Règles métier pures du domaine rib_alerts (sans FastAPI, sans I/O).

Comportement identique aux vérifications implicites des routeurs legacy.
"""
from __future__ import annotations

from typing import Optional

from app.modules.rib_alerts.domain.enums import RibAlertType
from app.modules.rib_alerts.domain.exceptions import MissingCompanyContextError


def require_company_id(company_id: Optional[str]) -> str:
    """
    Exige un contexte entreprise pour toute opération sur les alertes RIB.

    Comportement identique au legacy : 403 si active_company_id absent.
    """
    if not company_id or not str(company_id).strip():
        raise MissingCompanyContextError("Aucune entreprise active.")
    return str(company_id).strip()


def is_valid_alert_type(alert_type: Optional[str]) -> bool:
    """Vérifie que le type d’alerte est autorisé (filtre liste). None = pas de filtre."""
    if alert_type is None or alert_type == "":
        return True
    try:
        RibAlertType(alert_type)
        return True
    except ValueError:
        return False
