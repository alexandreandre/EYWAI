"""Schémas réponse — module Équipes."""

from typing import List, Optional

from pydantic import BaseModel


class TeamResponse(BaseModel):
    id: str
    company_id: str
    name: str
    description: Optional[str] = None
    color: str
    manager_employee_id: Optional[str] = None
    manager_first_name: Optional[str] = None
    manager_last_name: Optional[str] = None
    status: str
    employee_count: int = 0
    created_at: str
    updated_at: str


class TeamListResponse(BaseModel):
    teams: List[TeamResponse]
    total: int
    archived_count: int


class TeamAnalyticsItem(BaseModel):
    team_id: Optional[str] = None
    team_name: str
    team_color: str
    employee_count: int
    masse_salariale_brute: float
    masse_salariale_totale: float
    notes_de_frais: float
    absences_jours: float
    taux_absenteisme: float
    cout_moyen_par_salarie: float


class TeamAnalyticsResponse(BaseModel):
    period_start: str
    period_end: str
    items: List[TeamAnalyticsItem]
    total_employees: int
    total_masse_brute: float
    total_notes_de_frais: float


class TeamNameAvailabilityResponse(BaseModel):
    available: bool
    name: str


class TeamMemberItem(BaseModel):
    id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    job_title: Optional[str] = None


class TeamDetailPayload(BaseModel):
    team: TeamResponse
    members: List[TeamMemberItem]
