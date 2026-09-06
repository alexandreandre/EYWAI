"""
Schémas Pydantic entrée API du module expenses.

Migrés depuis schemas/expense.py — comportement identique.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

# Literals identiques au legacy (schemas/expense.py)
ExpenseStatus = Literal["pending", "validated", "rejected"]
ExpenseType = Literal[
    "Restaurant", "Transport", "Hôtel", "Fournitures", "Indemnités kilométriques", "Autre"
]
ExpenseStatusUpdateLiteral = Literal["validated", "rejected"]


class ExpenseBase(BaseModel):
    """Schéma de base pour une note de frais.

    `employee_id` est réservé aux RH (saisie pour un salarié) ; il est ignoré
    pour un collaborateur, dont la fiche est résolue depuis le compte connecté.
    """

    employee_id: str | None = None
    date: date
    amount: float = Field(..., gt=0, description="Montant TTC en euros")
    vat_rate: float = Field(
        ...,
        ge=0,
        le=100,
        description="Taux de TVA applicable en pourcentage (ex. 20, 10, 5.5)",
    )
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
