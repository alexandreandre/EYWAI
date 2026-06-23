"""Schémas de requête — import admin."""

from __future__ import annotations

from typing import List, Optional

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
