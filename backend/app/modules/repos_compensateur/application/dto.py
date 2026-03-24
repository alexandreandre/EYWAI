"""
DTOs (Data Transfer Objects) pour le module repos_compensateur.

Placeholder : à utiliser lors de la migration entre couches.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CreditRowInput:
    """Ligne de crédit à écrire (employee_id, year, month, source, heures, jours)."""

    employee_id: str
    company_id: str
    year: int
    month: int
    source: str
    heures: float
    jours: float


@dataclass
class CalculerCreditsResult:
    """Résultat du calcul des crédits (réponse applicative)."""

    company_id: str
    year: int
    month: int
    employees_processed: int
    credits_created: int
