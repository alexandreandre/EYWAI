"""Schémas API import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class DsnImportItemPreview(BaseModel):
    item_type: str
    source_ref: str
    action: str = "create"
    mapped_payload: Dict[str, Any] = Field(default_factory=dict)
    label: Optional[str] = None
    needs_review: Optional[bool] = None
    review_reasons: Optional[List[str]] = None
    preview_columns: Optional[Dict[str, Any]] = None
    employee_count: Optional[int] = None
    editable_fields: Optional[Dict[str, str]] = None
    is_scaffold: Optional[bool] = None
    is_existing: Optional[bool] = None
    existing_employee_id: Optional[str] = None
    existing_company_id: Optional[str] = None
    existing_company_name: Optional[str] = None


class DsnImportCompany(BaseModel):
    """Entreprise existante proposée pour le rattachement d'un import DSN."""

    id: str
    company_name: str
    siret: Optional[str] = None
    siren: Optional[str] = None
    group_id: Optional[str] = None
    group_name: Optional[str] = None
    is_active: bool = True


class DsnImportCompanyListResponse(BaseModel):
    companies: List[DsnImportCompany]


class DsnImportIssue(BaseModel):
    code: str
    message: str
    hint: Optional[str] = None
    severity: str = "error"
    source_ref: Optional[str] = None
    item_label: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


class DsnImportAnomaly(DsnImportIssue):
    type: str = ""

    @model_validator(mode="before")
    @classmethod
    def _normalize_anomaly_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        raw_type = str(out.get("type") or "")
        if not out.get("code"):
            if raw_type and raw_type not in ("error", "warning"):
                out["code"] = raw_type
            elif out.get("severity") == "blocking" or raw_type == "error":
                out["code"] = "validation_error"
            else:
                out["code"] = "validation_warning"
        if not out.get("type"):
            out["type"] = out["code"]
        return out


class DsnImportParseResponse(BaseModel):
    batch_id: str
    summary: Dict[str, Any]
    anomalies: List[DsnImportAnomaly]
    items: List[DsnImportItemPreview]
    can_commit: bool


class DsnImportCommitRequest(BaseModel):
    overrides: Dict[str, str] = Field(
        default_factory=dict,
        description="Map source_ref -> action (create|update|skip)",
    )


class ImportedEmployeeSummary(BaseModel):
    employee_id: str
    company_id: str
    full_name: str
    placeholder_email: Optional[str] = None
    employment_status: Optional[str] = None


class DsnImportCommitError(DsnImportIssue):
    pass


class DsnImportCommitResponse(BaseModel):
    stats: Dict[str, int]
    errors: List[DsnImportCommitError] = Field(default_factory=list)
    error_messages: List[str] = Field(default_factory=list)
    group_id: Optional[str] = None
    companies: Dict[str, str] = Field(default_factory=dict)
    imported_employees: List[ImportedEmployeeSummary] = Field(default_factory=list)


class DsnImportCommitStartResponse(BaseModel):
    """Réponse immédiate au lancement d'un commit asynchrone."""

    status: str = "committing"
    batch_id: str


class ActivateImportedEmployeeResponse(BaseModel):
    employee_id: str
    user_id: str
    email: str
    generated_password: str


class DsnImportBatchSummary(BaseModel):
    id: str
    uploaded_by: str
    file_names: List[str] = Field(default_factory=list)
    siren: Optional[str] = None
    period_min: Optional[str] = None
    period_max: Optional[str] = None
    status: str
    summary: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DsnImportBatchDetailResponse(BaseModel):
    batch: DsnImportBatchSummary
    items: List[Dict[str, Any]]
    preview: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)


class DsnImportBatchListResponse(BaseModel):
    batches: List[DsnImportBatchSummary]


class DsnImportRevalidateResponse(BaseModel):
    anomalies: List[DsnImportAnomaly]
    can_commit: bool
    summary: Dict[str, Any] = Field(default_factory=dict)
    items: List[DsnImportItemPreview] = Field(default_factory=list)


class DsnCoverageTimelineMonth(BaseModel):
    period: str
    month: int
    state: str


class DsnCoverageBatchRef(BaseModel):
    batch_id: str
    created_at: Optional[str] = None
    period_min: Optional[str] = None
    period_max: Optional[str] = None
    import_mode: Optional[str] = None
    periods: List[str] = Field(default_factory=list)


class DsnCoverageResponse(BaseModel):
    company_id: str
    dsn_sync_mode: str
    status: str
    expected_last_period: str
    next_import_period: Optional[str] = None
    last_period: Optional[str] = None
    last_import_at: Optional[str] = None
    months_covered: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    timeline: List[DsnCoverageTimelineMonth] = Field(default_factory=list)
    batch_count: int = 0
    recent_batches: List[DsnCoverageBatchRef] = Field(default_factory=list)
    alerts: List[Dict[str, Any]] = Field(default_factory=list)


class DsnCoverageAdminSummary(BaseModel):
    late_count: int
    companies: List[Dict[str, Any]] = Field(default_factory=list)
    all_companies: List[Dict[str, Any]] = Field(default_factory=list)


class DsnCoverageMatrixCompany(BaseModel):
    company_id: str
    company_name: Optional[str] = None
    group_name: Optional[str] = None
    siret: Optional[str] = None
    dsn_sync_mode: str
    status: str
    expected_last_period: str
    last_period: Optional[str] = None
    last_import_at: Optional[str] = None
    gaps_count: int = 0
    months_covered: List[str] = Field(default_factory=list)
    timeline: List[DsnCoverageTimelineMonth] = Field(default_factory=list)


class DsnCoverageAdminMatrixResponse(BaseModel):
    year: int
    companies: List[DsnCoverageMatrixCompany] = Field(default_factory=list)


class DsnImportRevokePeriodResponse(BaseModel):
    company_id: str
    period: str
    cumuls_deleted: int = 0
