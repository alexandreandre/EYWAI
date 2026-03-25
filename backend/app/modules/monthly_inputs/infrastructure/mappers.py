"""
Mappers monthly_inputs : conversion ligne DB <-> entité / DTO.

Placeholder minimal : l'API actuelle travaille en dict ; mappers à enrichir si besoin.
"""

from __future__ import annotations

from typing import Any, Dict
from uuid import UUID

from app.modules.monthly_inputs.domain.entities import MonthlyInputEntity


def _to_uuid(v: Any) -> UUID | None:
    if v is None:
        return None
    return v if isinstance(v, UUID) else UUID(str(v))


def row_to_entity(row: Dict[str, Any]) -> MonthlyInputEntity:
    """Convertit une ligne Supabase en MonthlyInputEntity (id/employee_id peuvent être str ou UUID)."""
    eid = row.get("employee_id")
    return MonthlyInputEntity(
        id=_to_uuid(row.get("id")),
        employee_id=(eid if isinstance(eid, UUID) else UUID(str(eid)))
        if eid is not None
        else UUID(int=0),
        year=row["year"],
        month=row["month"],
        name=row["name"],
        description=row.get("description"),
        amount=float(row["amount"]),
        is_socially_taxed=row.get("is_socially_taxed", True),
        is_taxable=row.get("is_taxable", True),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def entity_to_row(entity: MonthlyInputEntity) -> Dict[str, Any]:
    """Convertit une entité en dict pour insertion Supabase."""
    row: Dict[str, Any] = {
        "employee_id": str(entity.employee_id),
        "year": entity.year,
        "month": entity.month,
        "name": entity.name,
        "amount": entity.amount,
        "is_socially_taxed": entity.is_socially_taxed,
        "is_taxable": entity.is_taxable,
    }
    if entity.description is not None:
        row["description"] = entity.description
    if entity.id is not None:
        row["id"] = str(entity.id)
    return row
