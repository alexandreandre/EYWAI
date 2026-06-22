"""Schémas de réponse — import admin."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


MatchConfidence = Literal["high", "medium", "none"]
ReviewStatus = Literal["ok", "warning", "error"]
MatchMethod = Literal["matricule", "name_exact", "name_fuzzy", "email", "none"]


class RibImportRowPreview(BaseModel):
    row_index: int
    raw_identity: str = ""
    matricule: Optional[str] = None
    email: Optional[str] = None
    rib_raw: str = ""
    iban: str = ""
    bic: str = ""
    iban_valid: bool = False
    employee_id: Optional[str] = None
    matched_name: Optional[str] = None
    match_confidence: MatchConfidence = "none"
    match_method: MatchMethod = "none"
    review_status: ReviewStatus = "error"
    warnings: List[str] = Field(default_factory=list)
    current_iban_masked: Optional[str] = None
    raw_row: Dict[str, Any] = Field(default_factory=dict)


class RibImportRosterEmployee(BaseModel):
    id: str
    first_name: str
    last_name: str
    time_tracking_id: Optional[str] = None


class RibImportParseResponse(BaseModel):
    company_id: str
    company_name: str
    headers: List[str] = Field(default_factory=list)
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    rows: List[RibImportRowPreview] = Field(default_factory=list)
    roster: List[RibImportRosterEmployee] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)


class RibImportCommitResultItem(BaseModel):
    row_index: int
    employee_id: str
    success: bool
    message: str = ""
    duplicate_warnings: List[str] = Field(default_factory=list)


class RibImportCommitResponse(BaseModel):
    applied: int
    skipped: int
    results: List[RibImportCommitResultItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
