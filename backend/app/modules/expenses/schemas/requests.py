"""
Schémas Pydantic entrée API du module expenses.

Migrés depuis schemas/expense.py — comportement identique.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

# Literals identiques au legacy (schemas/expense.py)
ExpenseStatus = Literal["pending", "validated", "rejected"]
ExpenseType = Literal["Restaurant", "Transport", "Hôtel", "Fournitures", "Autre"]
ExpenseStatusUpdateLiteral = Literal["validated", "rejected"]


class ExpenseBase(BaseModel):
    """Schéma de base pour une note de frais (création côté client, sans employee_id)."""

    date: date
    amount: float
    type: ExpenseType
    description: str | None = None
    receipt_url: str | None = None
    filename: str | None = None


class ExpenseCreate(ExpenseBase):
    """Schéma création avec employee_id (usage interne ou admin)."""

    employee_id: str


class ExpenseStatusUpdateRequest(BaseModel):
    """Schéma pour la mise à jour du statut (validation / refus RH)."""

    status: ExpenseStatusUpdateLiteral


class SignedUploadUrlRequest(BaseModel):
    """Corps pour l'endpoint get-upload-url (filename dans le body)."""

    filename: str
