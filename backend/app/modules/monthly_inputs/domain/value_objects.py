"""
Value objects du domaine monthly_inputs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Period:
    """Période (année, mois) pour filtrer les saisies."""

    year: int
    month: int
