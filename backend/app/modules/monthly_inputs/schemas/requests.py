"""
Schémas requêtes du module monthly_inputs.

Alignés sur backend_api/schemas/monthly_input.py pour migration progressive.
Compatibilité : mêmes champs, types et défauts que l'existant.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MonthlyInput(BaseModel):
    """Modèle pour la table monthly_inputs (lecture + corps POST batch)."""

    id: Optional[UUID] = None
    employee_id: UUID
    year: int
    month: int
    name: str
    description: Optional[str] = None
    amount: float
    is_socially_taxed: bool = True
    is_taxable: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(json_encoders={UUID: str})


class MonthlyInputCreate(BaseModel):
    """Création d'une saisie (POST /api/employees/{id}/monthly-inputs). employee_id fourni par la route."""

    year: int
    month: int
    name: str
    description: Optional[str] = None
    amount: float
    is_socially_taxed: bool = True
    is_taxable: bool = True


class MonthlyInputsRequest(BaseModel):
    """Structure agrégée moteur de paie (primes, notes de frais, acompte). Réservé usage futur."""

    year: int
    month: int
    primes: list[dict] = []
    notes_de_frais: list[dict] = []
    acompte: Optional[float] = None
