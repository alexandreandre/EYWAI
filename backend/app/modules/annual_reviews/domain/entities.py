"""
Entités du domaine annual_reviews.

Placeholder : entité minimale pour évolution future. La lecture/écriture
repose aujourd'hui sur des dict (repository) et des schémas Pydantic.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Optional


@dataclass
class AnnualReview:
    """Entretien annuel (projection pour usage domain si besoin)."""

    id: str
    employee_id: str
    company_id: str
    year: int
    status: str
    planned_date: Optional[date] = None
    completed_date: Optional[date] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Champs optionnels métier (notes, compte-rendu, etc.)
    payload: Optional[Dict[str, Any]] = None

    @classmethod
    def from_row(cls, row: Dict[str, Any]) -> "AnnualReview":
        """Construction depuis une ligne DB (placeholder)."""
        return cls(
            id=row["id"],
            employee_id=row["employee_id"],
            company_id=row["company_id"],
            year=row["year"],
            status=row["status"],
            planned_date=row.get("planned_date"),
            completed_date=row.get("completed_date"),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
            payload=row,
        )
