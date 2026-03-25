"""
Value objects du domaine participation.

Placeholder : paramètres de répartition (salaire/presence %), etc.
À enrichir lors de la migration de la logique métier.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.participation.domain.enums import DistributionMode


@dataclass(frozen=True)
class ParticipationDistributionParams:
    """Paramètres de répartition de la participation (mode + pourcentages)."""

    mode: DistributionMode
    salaire_percent: int
    presence_percent: int
