"""
Schémas Pydantic sortie API du module expenses.

Migrés depuis schemas/expense.py — comportement identique.
SimpleEmployee importé depuis le module absences (même contrat que legacy).
"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.absences.schemas.responses import SimpleEmployee

# Literals pour cohérence (réponses API)
ExpenseStatusLiteral = Literal["pending", "validated", "rejected"]
ExpenseTypeLiteral = Literal["Restaurant", "Transport", "Hôtel", "Fournitures", "Autre"]


class Expense(BaseModel):
    """Note de frais telle que retournée par l'API (schéma legacy identique)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    created_at: datetime = Field(..., alias="created_at")
    employee_id: str
    date: date
    amount: float
    type: ExpenseTypeLiteral
    description: str | None = None
    receipt_url: str | None = None
    filename: str | None = None
    status: ExpenseStatusLiteral


class ExpenseWithEmployee(Expense):
    """Note de frais avec données employé (liste RH)."""

    employee: SimpleEmployee


class SignedUploadUrlResponse(BaseModel):
    """Réponse de l'endpoint get-upload-url (path + signedURL). Contrat API inchangé."""

    path: str
    signedURL: str  # camelCase pour le frontend
