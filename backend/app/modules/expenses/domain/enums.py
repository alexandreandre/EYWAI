"""
Énumérations du domaine expenses.

Alignées sur schemas/expense.py (ExpenseStatus, ExpenseType).
À utiliser par le domain et les schemas du module.
"""
from enum import Enum
from typing import Literal

# Literals pour compatibilité API (même valeurs que legacy)
ExpenseStatusLiteral = Literal["pending", "validated", "rejected"]
ExpenseTypeLiteral = Literal["Restaurant", "Transport", "Hôtel", "Fournitures", "Autre"]


class ExpenseStatus(str, Enum):
    """Statut d'une note de frais."""

    PENDING = "pending"
    VALIDATED = "validated"
    REJECTED = "rejected"


class ExpenseType(str, Enum):
    """Type de frais."""

    RESTAURANT = "Restaurant"
    TRANSPORT = "Transport"
    HOTEL = "Hôtel"
    FOURNITURES = "Fournitures"
    AUTRE = "Autre"
