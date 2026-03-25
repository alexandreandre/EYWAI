"""
Entités du domaine repos_compensateur.

Une ligne de crédit = employee_id, year, month, source, heures, jours.
À migrer depuis la structure utilisée dans services/repos_compensateur (repos_compensateur_credits).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=False)
class ReposCredit:
    """Crédit de repos (COR ou autre source) pour un employé, un mois, une année."""

    employee_id: str
    company_id: str
    year: int
    month: int
    source: str  # SourceCredit
    heures: float
    jours: float
