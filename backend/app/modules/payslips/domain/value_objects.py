"""
Value objects du domaine payslips.

Placeholders pour période (year/month) et identifiants. Optionnel en phase
de préparation ; utile pour règles métier et validation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PayslipPeriod:
    """Période d'un bulletin (année, mois)."""

    year: int
    month: int
