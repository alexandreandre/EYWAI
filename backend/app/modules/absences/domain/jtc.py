"""
JTC (Jour de Temps de Change) — droit annuel issu d'un accord d'entreprise.

Note de paramétrage Elsa André du 28/07/2026 : 3 jours par an au maximum pour
une année complète de travail effectif, proratisés sur l'année civile N-1,
arrondis à l'entier inférieur. Le dispositif n'est prévu par aucune convention
de branche : il n'existe que pour les sociétés qui l'ont activé.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

JTC_ANNUAL_DAYS_DEFAULT = 3
JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT = 30
# Absences citées par la note : maladie, AT, maternité, « et autres absences ».
# L'onglet de détail annoncé n'ayant pas été transmis, les congés sans solde
# tiennent lieu d'« autres absences » jusqu'à confirmation.
JTC_ABSENCE_TYPES_DEFAULT: tuple[str, ...] = (
    "arret_maladie",
    "arret_at",
    "arret_maladie_pro",
    "arret_maternite",
    "sans_solde",
)


@dataclass(frozen=True)
class JtcSettings:
    """Paramètres JTC d'une société. Désactivé par défaut : seule MBC l'active."""

    enabled: bool = False
    annual_days: int = JTC_ANNUAL_DAYS_DEFAULT
    absence_threshold_days: int = JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT
    absence_types: tuple[str, ...] = JTC_ABSENCE_TYPES_DEFAULT


def _days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def _presence_days(
    reference_year: int, hire_date: date, exit_date: date | None
) -> int:
    """Jours calendaires de présence du salarié sur l'année de référence."""
    year_start = date(reference_year, 1, 1)
    year_end = date(reference_year, 12, 31)
    start = max(hire_date, year_start)
    end = min(exit_date, year_end) if exit_date else year_end
    if end < start:
        return 0
    return (end - start).days + 1


def calculate_acquired_jtc(
    *,
    settings: JtcSettings,
    reference_year: int,
    hire_date: date | None,
    exit_date: date | None = None,
    absence_days: float = 0.0,
) -> int:
    """
    Droit JTC de l'année N, acquis sur l'activité de `reference_year` (N-1).

    Le droit plein est réduit dans deux cas cumulables : entrée ou sortie en
    cours d'année de référence, et absences dépassant le seuil paramétré. Sous
    le seuil, les absences n'ont aucun effet ; au-dessus, elles sont déduites
    en totalité. Le résultat est arrondi à l'entier inférieur et borné au droit
    annuel.
    """
    if not settings.enabled or hire_date is None:
        return 0

    days_in_year = _days_in_year(reference_year)
    presence = _presence_days(reference_year, hire_date, exit_date)
    if presence <= 0:
        return 0

    deducted = absence_days if absence_days > settings.absence_threshold_days else 0.0
    effective = max(0.0, presence - deducted)

    acquired = settings.annual_days * effective / days_in_year
    return max(0, min(settings.annual_days, int(acquired)))
