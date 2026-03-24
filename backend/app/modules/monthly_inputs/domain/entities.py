"""
Entités du domaine monthly_inputs.

Représentation métier d'une saisie mensuelle (prime, acompte, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID


@dataclass
class MonthlyInputEntity:
    """Saisie mensuelle : élément variable de paie pour un employé / mois."""

    employee_id: UUID
    year: int
    month: int
    name: str
    amount: float
    description: Optional[str] = None
    is_socially_taxed: bool = True
    is_taxable: bool = True
    id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
