"""
DTOs du module expenses (entrées/sorties application).

Alignés sur le comportement de api/routers/expenses.py.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class CreateExpenseInput:
    """Entrée pour la création d'une note de frais."""

    employee_id: str
    date: date
    amount: float
    vat_rate: float
    type: str
    description: Optional[str] = None
    receipt_url: Optional[str] = None
    filename: Optional[str] = None
    company_id: Optional[str] = None
    initial_status: Optional[str] = None


@dataclass
class UpdateExpenseInput:
    """Entrée pour la modification des champs d'une note (RH)."""

    expense_id: str
    date: Optional[date] = None
    amount: Optional[float] = None
    vat_rate: Optional[float] = None
    type: Optional[str] = None
    description: Optional[str] = None
    # None peut vouloir dire « effacer » : la sentinelle distingue « absent ».
    description_definie: bool = False


@dataclass
class UpdateExpenseStatusInput:
    """Entrée pour la mise à jour du statut (validated | rejected)."""

    expense_id: str
    status: str


@dataclass
class SignedUploadUrlOutput:
    """Sortie get-upload-url (path + signedURL)."""

    path: str
    signed_url: str


@dataclass
class ListExpensesInput:
    """Entrée pour la liste RH (optionnel filtre status)."""

    status: Optional[str] = None
