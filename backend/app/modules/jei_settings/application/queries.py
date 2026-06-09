"""Lecture paramètres JEI."""

from __future__ import annotations

from datetime import date
from typing import Optional, Tuple

from app.modules.jei_settings.infrastructure.repository import jei_settings_repository
from app.modules.jei_settings.schemas.responses import JeiSettings

_DUREE_JEI_ANNEES = 7


def _eligibilite_dates(
    date_creation: Optional[date],
) -> Tuple[Optional[date], Optional[int]]:
    """Retourne (date_fin_eligibilite, annees_restantes) à partir d'aujourd'hui."""
    if not date_creation:
        return None, None
    fin = date(date_creation.year + _DUREE_JEI_ANNEES, 12, 31)
    today = date.today()
    if today > fin:
        return fin, 0
    annees_restantes = fin.year - today.year
    if (fin.month, fin.day) < (today.month, today.day):
        annees_restantes -= 1
    return fin, max(0, annees_restantes)


def _defaults(company_id: str) -> JeiSettings:
    return JeiSettings(
        id=None,
        company_id=company_id,
        jei_enabled=False,
        date_creation_etablissement=None,
        taux_exoneration=1.0,
        annees_restantes=None,
        date_fin_eligibilite=None,
        created_at=None,
        updated_at=None,
    )


def get_jei_settings(company_id: str) -> JeiSettings:
    """Retourne la config ou les valeurs par défaut si aucune ligne."""
    raw = jei_settings_repository.get_by_company(company_id)
    if not raw:
        return _defaults(company_id)
    settings = JeiSettings.model_validate(raw)
    fin, restantes = _eligibilite_dates(settings.date_creation_etablissement)
    settings.date_fin_eligibilite = fin
    settings.annees_restantes = restantes
    return settings


def get_jei_settings_raw(company_id: str) -> JeiSettings:
    """Lecture sans enrichissement UI (moteur paie)."""
    raw = jei_settings_repository.get_by_company(company_id)
    if not raw:
        return _defaults(company_id)
    return JeiSettings.model_validate(raw)
