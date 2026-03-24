"""
Value objects du domaine expenses.

Optionnels : montant, période, etc. À enrichir lors de la migration.
"""
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class ExpenseAmount:
    """Montant d'une note de frais (placeholder pour règles métier)."""

    value: float
    currency: str = "EUR"
