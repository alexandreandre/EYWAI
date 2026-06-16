"""
DTOs applicatifs du module companies.

Structure cible pour les retours des queries/commands (details+kpis, settings).
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CompanyDetailsWithKpisDto:
    """Résultat de get_company_details_and_kpis (contract API inchangé)."""

    company_data: Dict[str, Any]
    kpis: Dict[str, Any]


@dataclass
class CompanySettingsResultDto:
    """Résultat de get_company_settings / update_company_settings."""

    medical_follow_up_enabled: bool
    settings: Dict[str, Any]


@dataclass
class CompanyOverviewDto:
    """Résultat de get_company_overview."""

    demographics: Dict[str, Any]
    movements: Dict[str, Any]
    absenteeism: Dict[str, Any]
    alerts: list
    compliance: Dict[str, Any]
    cdd_ending_within_30_days: int
    dsn_coverage: Optional[Dict[str, Any]] = None
