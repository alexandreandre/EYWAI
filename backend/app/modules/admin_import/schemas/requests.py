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
