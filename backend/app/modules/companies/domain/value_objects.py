"""
Value objects du domaine companies.

Placeholder : structure cible pour settings et KPIs.
"""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class CompanySettings:
    """Settings entreprise (ex. medical_follow_up_enabled)."""
    raw: Dict[str, Any]

    @property
    def medical_follow_up_enabled(self) -> bool:
        return bool(self.raw.get("medical_follow_up_enabled"))


# Placeholder : KpiSnapshot ou structures pour evolution_12_months, etc.
# À compléter lors de la migration du calcul des KPIs depuis le router.
