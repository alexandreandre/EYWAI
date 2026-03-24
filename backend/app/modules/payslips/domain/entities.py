"""
Entités du domaine payslips.

Placeholder pour agrégat Payslip. La migration pourra introduire une entité
riche ; pour l'instant on travaille en dict/DTO pour compatibilité legacy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Payslip:
    """
    Agrégat bulletin de paie (placeholder).

    Lors de la migration complète, remplacer les dict par cette entité
    et faire mapper l'infrastructure vers elle.
    """
    id: str
    employee_id: str
    company_id: str
    month: int
    year: int
    payslip_data: dict[str, Any]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> Payslip:
        """Construction depuis une ligne BDD (placeholder)."""
        return cls(
            id=row["id"],
            employee_id=row["employee_id"],
            company_id=row["company_id"],
            month=row["month"],
            year=row["year"],
            payslip_data=row.get("payslip_data") or {},
        )
