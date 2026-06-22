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


class CpImportRowPreview(BaseModel):
    row_index: int
    source_file: str = ""
    page_index: int = 0
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    siret: Optional[str] = None
    period_label: Optional[str] = None
    year: int
    month: Optional[int] = None
    raw_identity: str = ""
    matricule: Optional[str] = None
    cp_n1_solde: float = 0.0
    cp_n_solde: float = 0.0
    acquis_n1: Optional[float] = None
    acquis_n: Optional[float] = None
    pris_n1: Optional[float] = None
    pris_n: Optional[float] = None
    employee_id: Optional[str] = None
    matched_name: Optional[str] = None
    match_confidence: MatchConfidence = "none"
    match_method: MatchMethod = "none"
    review_status: ReviewStatus = "error"
    warnings: List[str] = Field(default_factory=list)
    parse_format: str = "unknown"
    current_cp_n1: Optional[float] = None
    current_cp_n: Optional[float] = None
    delta_cp_n1: Optional[float] = None
    delta_cp_n: Optional[float] = None
    has_existing_adjustment: bool = False


class CpImportRosterEmployee(BaseModel):
    id: str
    first_name: str
    last_name: str
    time_tracking_id: Optional[str] = None


class CpImportParseResponse(BaseModel):
    rows: List[CpImportRowPreview] = Field(default_factory=list)
    rosters_by_company: Dict[str, List[CpImportRosterEmployee]] = Field(
        default_factory=dict
    )
    summary: Dict[str, int] = Field(default_factory=dict)
    file_errors: List[str] = Field(default_factory=list)


class CpImportCommitResultItem(BaseModel):
    row_index: int
    employee_id: str
    success: bool
    message: str = ""
    duplicate_warnings: List[str] = Field(default_factory=list)


class CpImportCommitResponse(BaseModel):
    applied: int
    skipped: int
    results: List[CpImportCommitResultItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
