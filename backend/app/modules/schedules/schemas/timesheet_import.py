"""Schémas API import pointages (staging batch/items, profils entreprise)."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.modules.schedules.schemas.ai import AiCalendarProposalResponse

BatchStatus = Literal[
    "parsed", "previewed", "committing", "committed", "failed", "cancelled"
]
SourceType = Literal[
    "document_pdf", "document_image", "csv", "xlsx", "badgeuse", "nl_text"
]
ItemMatchStatus = Literal["matched", "ambiguous", "unmatched", "skipped"]


class TimesheetImportProfile(BaseModel):
    id: Optional[str] = None
    company_id: Optional[str] = None
    profile_name: str = "default"
    source_type: SourceType = "csv"
    parser_key: str = "tabular_generic"
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)


class TimesheetImportProfileUpdate(BaseModel):
    profile_name: str = "default"
    source_type: SourceType = "csv"
    parser_key: str = "tabular_generic"
    column_mapping: Dict[str, str] = Field(default_factory=dict)
    options: Dict[str, Any] = Field(default_factory=dict)


class ColumnDetectionResponse(BaseModel):
    headers: List[str] = Field(default_factory=list)
    sample_rows: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_mapping: Dict[str, str] = Field(default_factory=dict)
    mapping_complete: bool = False
    source_type: SourceType = "csv"


class TimesheetImportBatchSummary(BaseModel):
    employees_total: int = 0
    employees_matched: int = 0
    days_total: int = 0
    coverage_avg: Optional[float] = None
    tokens_used: int = 0
    committed_days: int = 0
    commit_progress: Optional[Dict[str, Any]] = None
    # Refus de commit (ex. absence validée préservée) : sans ce champ,
    # Pydantic strippe la liste et la RH ne voit jamais les jours refusés.
    commit_warnings: Optional[List[Dict[str, Any]]] = None


class TimesheetImportParseResponse(BaseModel):
    batch_id: str
    status: BatchStatus = "previewed"
    preview: AiCalendarProposalResponse
    parser_key: Optional[str] = None
    file_hash: Optional[str] = None
    duplicate_of_batch_id: Optional[str] = None


class TimesheetImportBatchResponse(BaseModel):
    batch_id: str
    status: BatchStatus
    preview: Optional[AiCalendarProposalResponse] = None
    summary: TimesheetImportBatchSummary = Field(
        default_factory=TimesheetImportBatchSummary
    )
    parser_key: Optional[str] = None
    source_type: Optional[SourceType] = None
    filename: Optional[str] = None
    period_year: Optional[int] = None
    period_month: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    error_message: Optional[str] = None
    import_job_id: Optional[str] = None


class TimesheetImportCommitStartResponse(BaseModel):
    batch_id: str
    status: Literal["committing"] = "committing"


class TimesheetImportCommitRequest(BaseModel):
    allow_partial: bool = False
    recalculate_payroll: bool = False
    employee_ids: Optional[List[str]] = None


class TimesheetImportCommitResult(BaseModel):
    batch_id: str
    status: BatchStatus
    employees_processed: int = 0
    total_days_written: int = 0
    errors: List[Dict[str, str]] = Field(default_factory=list)


class TimesheetImportMultiStartResponse(BaseModel):
    job_id: str
    batch_id: str
    status: str = "extracting"
    file_count: int = 1


__all__ = [
    "BatchStatus",
    "ColumnDetectionResponse",
    "ItemMatchStatus",
    "SourceType",
    "TimesheetImportBatchResponse",
    "TimesheetImportBatchSummary",
    "TimesheetImportCommitRequest",
    "TimesheetImportCommitResult",
    "TimesheetImportCommitStartResponse",
    "TimesheetImportMultiStartResponse",
    "TimesheetImportParseResponse",
    "TimesheetImportProfile",
    "TimesheetImportProfileUpdate",
]
