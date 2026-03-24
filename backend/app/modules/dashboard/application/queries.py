"""
Cas d'usage lecture du module dashboard.

Délègue au service applicatif ; pas de logique métier ici.
"""
from __future__ import annotations

from app.modules.dashboard.application.service import (
    build_full_dashboard,
    get_residence_permit_stats as _get_residence_permit_stats,
)
from app.modules.dashboard.schemas.responses import DashboardData, ResidencePermitStats


def get_dashboard_data(company_id: str) -> DashboardData:
    """
    Agrège toutes les données du cockpit RH pour une entreprise.
    Délègue à build_full_dashboard.
    """
    return build_full_dashboard(company_id)


def get_residence_permit_stats(company_id: str) -> ResidencePermitStats:
    """
    Retourne les statistiques agrégées des titres de séjour pour le dashboard.
    Délègue au service (calcul via app.shared.infrastructure.residence_permit).
    """
    return _get_residence_permit_stats(company_id)
