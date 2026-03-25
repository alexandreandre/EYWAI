"""
DTOs applicatifs du module companies.

Structure cible pour les retours des queries/commands (details+kpis, settings).
"""

from dataclasses import dataclass
from typing import Any, Dict


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
