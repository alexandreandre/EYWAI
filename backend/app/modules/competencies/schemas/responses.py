"""Schémas de réponse API compétences."""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CompetencyRef(BaseModel):
    id: str
    company_id: str
    name: str
    category: str
    description: Optional[str] = None
    required_level: Optional[int] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EmployeeCompetency(BaseModel):
    id: str
    company_id: str
    employee_id: str
    competency_id: str
    score: int = Field(ge=0, le=4)
    evaluation_date: date
    evaluated_by: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[datetime] = None
    competency_name: Optional[str] = None
    competency_category: Optional[str] = None
    required_level: Optional[int] = None
    employee_name: Optional[str] = None
    is_gap: bool = False


class MatrixCell(BaseModel):
    employee_id: str
    employee_name: str
    competency_id: str
    competency_name: str
    score: int = Field(ge=0, le=4)
    required_level: Optional[int] = None
    is_gap: bool = False


class CompetencyMatrix(BaseModel):
    employees: List[dict]
    competencies: List[dict]
    cells: List[MatrixCell]
    gaps: List[MatrixCell]
    gap_trainings: List[dict] = Field(
        default_factory=list,
        description="Formations catalogue liées (competency_id) pour les gaps",
    )


class MobilityRecommendedPosition(BaseModel):
    poste: str
    compatibilite: int = Field(ge=0, le=100)
    points_forts: List[str]
    competences_a_developper: List[str]


class MobilityRecommendedTraining(BaseModel):
    training_id: str | None = None
    titre: str
    priorite: str
    competence_ciblee: str
    impact_estime: str


class MobilityAnalysis(BaseModel):
    employee_id: str
    mobilite_score: int = Field(ge=0, le=100)
    potentiel_evolution: str
    postes_recommandes: List[MobilityRecommendedPosition]
    formations_recommandees: List[MobilityRecommendedTraining]
    synthese: str
    analyzed_at: datetime
