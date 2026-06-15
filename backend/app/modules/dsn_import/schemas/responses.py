"""Schémas API import DSN."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DsnImportItemPreview(BaseModel):
    item_type: str
    source_ref: str
    action: str = "create"
    mapped_payload: Dict[str, Any] = Field(default_factory=dict)
    label: Optional[str] = None
    needs_review: Optional[bool] = None
    employee_count: Optional[int] = None


class DsnImportAnomaly(BaseModel):
    type: str
    message: str
    severity: str = "warning"
    source_ref: Optional[str] = None


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


class DsnImportCommitResponse(BaseModel):
    stats: Dict[str, int]
    errors: List[str]
    group_id: Optional[str] = None
    companies: Dict[str, str] = Field(default_factory=dict)
    imported_employees: List[ImportedEmployeeSummary] = Field(default_factory=list)


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
