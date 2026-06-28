"""Schémas de requête — import admin."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RibImportCommitRow(BaseModel):
    row_index: int
    employee_id: str
    iban: str
    bic: Optional[str] = None
    confirmed: bool = True


class RibImportCommitBody(BaseModel):
    company_id: str
    rows: List[RibImportCommitRow] = Field(default_factory=list)


class SeniorityImportCommitRow(BaseModel):
    row_index: int
    employee_id: str
    seniority_date: str
    confirmed: bool = True


class SeniorityImportCommitBody(BaseModel):
    company_id: str
    rows: List[SeniorityImportCommitRow] = Field(default_factory=list)


class CpImportCommitRow(BaseModel):
    row_index: int
    company_id: str
    employee_id: str
    year: int
    month: Optional[int] = Field(None, ge=1, le=12)
    cp_n1_solde: float = 0.0
    cp_n_solde: float = 0.0
    source_file: Optional[str] = None
    period_label: Optional[str] = None
    confirmed: bool = True


class CpImportCommitBody(BaseModel):
    rows: List[CpImportCommitRow] = Field(default_factory=list)


class PayrollExportCommitRow(BaseModel):
    row_index: int
    employee_id: str
    employee_patch: Dict[str, Any] = Field(default_factory=dict)
    team_name: Optional[str] = None
    boeth: Optional[Dict[str, Any]] = None
    confirmed: bool = True


class PayrollExportCommitBody(BaseModel):
    company_id: str
    create_teams_if_missing: bool = True
    rows: List[PayrollExportCommitRow] = Field(default_factory=list)


class PlanningImportManualMapping(BaseModel):
    raw_name: str = Field(..., min_length=1)
    employee_id: str = Field(..., min_length=1)


class PlanningImportApplyMappingsBody(BaseModel):
    batch_id: str
    company_id: str
    mappings: List[PlanningImportManualMapping] = Field(default_factory=list)
