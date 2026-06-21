"""Schémas API — revue pré-paie (anomalies)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

PreflightAnomalyType = Literal[
    "ecart_heures",
    "heures_non_saisies",
    "pointage",
    "conflit_absence",
    "hs_routing_pending",
    "hs_pointage_a_valider",
]

PreflightAnomalySeverity = Literal["bloquant", "a_verifier"]

PreflightAnomalyStatus = Literal["a_traiter", "justifie", "resolu"]

PreflightResolutionMotif = Literal[
    "directeur_site",
    "heures_sup",
    "erreur_pointage_corrigee",
    "autre",
]


class PreflightDayEcartDetail(BaseModel):
    jour: int
    heures_prevues: float
    heures_faites: float
    ecart: float
    heures_sup: bool = False


class PreflightAnomalyResolution(BaseModel):
    status: PreflightAnomalyStatus
    motif: Optional[PreflightResolutionMotif] = None
    commentaire: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None


class PreflightAnomaly(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    team_id: Optional[str] = None
    type: PreflightAnomalyType
    severity: PreflightAnomalySeverity
    status: PreflightAnomalyStatus
    heures_prevues: Optional[float] = None
    heures_faites: Optional[float] = None
    ecart: Optional[float] = None
    is_forfait_jour: bool = False
    sub_type: Optional[str] = None
    detail_jours: List[PreflightDayEcartDetail] = Field(default_factory=list)
    conflict_days: List[int] = Field(default_factory=list)
    days_with_pointage_anomalies: Optional[int] = None
    message: Optional[str] = None
    resolution: Optional[PreflightAnomalyResolution] = None


class PreflightAnomalyCounts(BaseModel):
    ecart_heures: int = 0
    heures_non_saisies: int = 0
    pointage: int = 0
    conflit_absence: int = 0
    hs_routing_pending: int = 0
    hs_pointage_a_valider: int = 0
    bloquant: int = 0
    a_verifier: int = 0


class PreflightAnomaliesResponse(BaseModel):
    year: int
    month: int
    total: int
    total_open: int
    total_treated: int
    counts: PreflightAnomalyCounts
    anomalies: List[PreflightAnomaly] = Field(default_factory=list)
