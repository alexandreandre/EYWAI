"""
Entités du domaine expenses.

Alignées sur la table expense_reports et les schémas legacy (schemas/expense.py).
Pas de dépendance DB ni FastAPI.
À remplir lors de la migration depuis api/routers/expenses.py.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional


@dataclass
class ExpenseReportEntity:
    """
    Note de frais (agrégat racine).
    Source : table expense_reports, schémas schemas/expense.py.
    """

    id: str
    employee_id: str
    date: date
    amount: float
    type: str  # ExpenseType
    status: str  # ExpenseStatus
    company_id: Optional[str] = None
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    filename: Optional[str] = None
    created_at: Optional[datetime] = None
