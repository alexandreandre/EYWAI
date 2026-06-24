"""Schémas de réponse — import admin."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


MatchConfidence = Literal["high", "medium", "none"]
ReviewStatus = Literal["ok", "warning", "error"]
MatchMethod = Literal[
    "nir",
    "matricule",
    "name_exact",
    "name_fuzzy",
    "email",
    "patronymic",
    "patronymic_matricule",
    "none",
]


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


class PayrollExportRowPreview(BaseModel):
    row_index: int
    raw_identity: str = ""
    nir: Optional[str] = None
    email: Optional[str] = None
    employee_id: Optional[str] = None
    matched_name: Optional[str] = None
    match_confidence: MatchConfidence = "none"
    match_method: MatchMethod = "none"
    review_status: ReviewStatus = "error"
    warnings: List[str] = Field(default_factory=list)
    preview_columns: Dict[str, Any] = Field(default_factory=dict)
    employee_patch: Dict[str, Any] = Field(default_factory=dict)
    boeth: Optional[Dict[str, Any]] = None
    team_name: Optional[str] = None
    current_email: Optional[str] = None
    raw_row: Dict[str, Any] = Field(default_factory=dict)


class PayrollExportParseResponse(BaseModel):
    company_id: str
    company_name: str
    headers: List[str] = Field(default_factory=list)
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    rows: List[PayrollExportRowPreview] = Field(default_factory=list)
    roster: List[RibImportRosterEmployee] = Field(default_factory=list)
    summary: Dict[str, int] = Field(default_factory=dict)


class PayrollExportCommitResultItem(BaseModel):
    row_index: int
    employee_id: str
    success: bool
    message: str = ""
    duplicate_warnings: List[str] = Field(default_factory=list)


class PayrollExportCommitResponse(BaseModel):
    applied: int
    skipped: int
    results: List[PayrollExportCommitResultItem] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class CompanySetupNextAction(BaseModel):
    block: str
    label: str
    tab: str
    priority: int = 0


class CompanySetupStatusResponse(BaseModel):
    company_id: str
    company_name: str
    idcc: Optional[str] = None
    overall_pct: float = 0.0
    blocks: Dict[str, Any] = Field(default_factory=dict)
    next_actions: List[CompanySetupNextAction] = Field(default_factory=list)


class CcnPresetApplyResponse(BaseModel):
    company_id: str
    idcc: Optional[str] = None
    leave_preset_applied: bool = False
    modulation_preset_applied: bool = False


class PlanningImportParseResponse(BaseModel):
    company_id: str
    company_name: str
    year: int
    month: int
    period_mode: str = "month"
    batch_id: str
    status: str = "previewed"
    preview: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    roster: List[Dict[str, Any]] = Field(default_factory=list)
    parser_key: Optional[str] = None
    file_hash: Optional[str] = None


class PlanningImportApplyMappingsResponse(BaseModel):
    batch_id: str
    summary: Dict[str, Any]


class PlanningImportCommitResponse(BaseModel):
    batch_id: str
    status: str = "committing"
    employees_processed: int = 0
    total_days_written: int = 0
    errors: List[Dict[str, str]] = Field(default_factory=list)


class PlanningImportBatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    summary: Dict[str, Any] = Field(default_factory=dict)
    commit_progress: Optional[Dict[str, Any]] = None
    employees_processed: Optional[int] = None
    total_days_written: Optional[int] = None
    errors: List[Dict[str, str]] = Field(default_factory=list)
    error_message: Optional[str] = None
