"""
Mappers dict/row DB <-> domain entities.

Comportement identique aux écritures/lectures actuelles (repos_compensateur_credits).
"""
from __future__ import annotations

from typing import Any

from app.modules.repos_compensateur.domain.entities import ReposCredit


def credit_to_row(credit: ReposCredit) -> dict[str, Any]:
    """ReposCredit -> dict pour upsert Supabase."""
    return {
        "employee_id": credit.employee_id,
        "company_id": credit.company_id,
        "year": credit.year,
        "month": credit.month,
        "source": credit.source,
        "heures": credit.heures,
        "jours": credit.jours,
    }


def row_to_credit(row: dict[str, Any]) -> ReposCredit:
    """Row Supabase -> ReposCredit."""
    return ReposCredit(
        employee_id=str(row["employee_id"]),
        company_id=str(row["company_id"]),
        year=int(row["year"]),
        month=int(row["month"]),
        source=str(row.get("source", "cor")),
        heures=float(row.get("heures", 0)),
        jours=float(row.get("jours", 0)),
    )
