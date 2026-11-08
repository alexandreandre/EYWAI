"""Ce qui rend le test du théorème capable de rougir : le bilan, les salariés à jouer.

Sans effet à l'import (pas de piège, pas de base) : les tests unitaires le lisent
tel quel. Le script `theoreme_correction_a_la_main.py` s'en sert.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from app.shared.domain.employment_rules import payslip_employment_period_block_reason


@dataclass(frozen=True)
class Bilan:
    joues: int
    sautes: int
    echecs: int

    @property
    def code(self) -> int:
        """1 si un cas échoue, ou si rien n'a été joué : un test à vide n'est pas vert."""
        return 1 if self.echecs or not self.joues else 0

    @property
    def phrase(self) -> str:
        return f"{self.joues} cas joué(s), {self.sautes} sauté(s), {self.echecs} échec(s)" + (
            "" if self.joues else " — 0 cas : RIEN N'A ÉTÉ PROUVÉ"
        )


def bilan(rapport: Iterable[Mapping[str, Any]]) -> Bilan:
    cas = list(rapport)
    sautes = sum(1 for c in cas if c.get("saute"))
    return Bilan(joues=len(cas) - sautes, sautes=sautes, echecs=sum(1 for c in cas if not c.get("ok")))


def salaries_a_jouer(employes: Iterable[dict[str, Any]], year: int, month: int) -> list[dict[str, Any]]:
    """Les salariés présents dans le mois, lus sur la fiche : un mois sans bulletin se joue aussi."""
    return [e for e in employes if payslip_employment_period_block_reason(e, year, month) is None]
