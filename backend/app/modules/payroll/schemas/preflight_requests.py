"""Schémas requêtes — revue pré-paie (anomalies)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.modules.payroll.schemas.preflight_responses import (
    PreflightAnomalyType,
    PreflightResolutionMotif,
)


class PreflightResolutionRequest(BaseModel):
    employee_id: str
    anomaly_type: PreflightAnomalyType
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    motif: PreflightResolutionMotif
    commentaire: Optional[str] = Field(None, max_length=2000)


class PreflightResolutionDeleteRequest(BaseModel):
    employee_id: str
    anomaly_type: PreflightAnomalyType
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)


class PreflightAcknowledgeRequest(BaseModel):
    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    open_anomalies_count: int = Field(..., ge=0)
    anomaly_types_summary: List[str] = Field(default_factory=list)
    commentaire: Optional[str] = Field(None, max_length=2000)
