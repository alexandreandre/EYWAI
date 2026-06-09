"""Règles métier OETH pures."""

from __future__ import annotations

from datetime import date
from typing import Optional


def coefficient_taille(ema_assujettissement: float, config: dict) -> int:
    """Coefficient 400 / 500 / 600 selon l'EMA d'assujettissement."""
    coeffs = config.get("coefficients", {})
    if ema_assujettissement >= 750:
        return int(coeffs.get("750_plus", 600))
    if ema_assujettissement >= 250:
        return int(coeffs.get("250_749", 500))
    return int(coeffs.get("20_249", 400))


def is_neutralisation_active(
    date_franchissement: Optional[date],
    employment_year: int,
    config: dict,
) -> bool:
    """Période de neutralisation : 5 ans après franchissement du seuil de 20 salariés."""
    if not date_franchissement:
        return False
    years = int(config.get("neutralisation_years", 5))
    end_year = date_franchissement.year + years - 1
    return employment_year <= end_year


def is_accord_agree_active(
    code: Optional[str],
    valid_from: Optional[date],
    valid_to: Optional[date],
    employment_year: int,
) -> bool:
    if not code or code in ("D00000000001",):
        return False
    year_start = date(employment_year, 1, 1)
    year_end = date(employment_year, 12, 31)
    if valid_from and valid_from > year_end:
        return False
    if valid_to and valid_to < year_start:
        return False
    return True


def boeth_50_plus_factor(
    date_naissance: Optional[date],
    employment_year: int,
    config: dict,
) -> float:
    """BOETH ≥ 50 ans (ou atteignant 50 ans dans l'année) comptés à 150 %."""
    if not date_naissance:
        return 1.0
    age_end = employment_year - date_naissance.year
    if (date_naissance.month, date_naissance.day) > (12, 31):
        age_end -= 1
    if age_end >= 50:
        return float(config.get("boeth_50_plus_factor", 1.5))
    if date_naissance.year + 50 == employment_year:
        return float(config.get("boeth_50_plus_factor", 1.5))
    return 1.0


def quota_boeth(ema_assujettissement: float, taux_obligation: float) -> int:
    """Nombre de BOETH à employer (arrondi entier inférieur)."""
    import math

    return math.floor(ema_assujettissement * taux_obligation)


def round_euro(amount: float) -> float:
    return round(amount + 1e-9, 2)
