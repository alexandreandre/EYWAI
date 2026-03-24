"""
Schémas de réponse API pour participation (Participation & Intéressement).

Migrés depuis api/routers/participation.py — comportement identique.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel


class ParticipationSimulationResponse(BaseModel):
    """Modèle pour la réponse d'une simulation"""

    id: UUID
    company_id: UUID
    year: int
    simulation_name: str
    benefice_net: float
    capitaux_propres: float
    salaires_bruts: float
    valeur_ajoutee: float
    participation_mode: str
    participation_salaire_percent: int
    participation_presence_percent: int
    interessement_enabled: bool
    interessement_envelope: Optional[float]
    interessement_mode: Optional[str]
    interessement_salaire_percent: int
    interessement_presence_percent: int
    results_data: Dict[str, Any]
    created_at: datetime
    created_by: Optional[UUID]
    updated_at: datetime


class ParticipationSimulationListItem(BaseModel):
    """Modèle pour la liste des simulations"""

    id: UUID
    year: int
    simulation_name: str
    created_at: datetime
    updated_at: datetime


class EmployeeParticipationDataItem(BaseModel):
    """Données d'un employé pour le simulateur (GET /employee-data/{year})."""

    employee_id: str
    first_name: str
    last_name: str
    annual_salary: float
    presence_days: int
    seniority_years: int
    has_real_salary: bool
    has_real_presence: bool


class EmployeeDataResponse(BaseModel):
    """Réponse de l'endpoint employee-data : liste employés + année."""

    employees: List[EmployeeParticipationDataItem]
    year: int
