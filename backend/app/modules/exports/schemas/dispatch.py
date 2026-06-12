from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .responses import ExportFileInfo, ExportTotals

DispatchChannel = Literal["compta", "banque"]
DispatchStatus = Literal["pending", "generated", "transmitted", "failed"]


class DispatchBlockingAnomaly(BaseModel):
    source_key: str
    source_label: str
    message: str
    employee_id: Optional[str] = None
    employee_name: Optional[str] = None
    action_label: str
    action_path: str
    context_note: Optional[str] = None
    balance_debug: Optional[Dict[str, Any]] = None


class DispatchChannelStatus(BaseModel):
    channel: DispatchChannel
    period: str
    status: DispatchStatus
    dispatch_id: Optional[str] = None
    export_ids: List[str] = Field(default_factory=list)
    files_count: int = 0
    totals: Optional[ExportTotals] = None
    generated_at: Optional[datetime] = None
    transmitted_at: Optional[datetime] = None
    transmission_note: Optional[str] = None
    can_generate: bool = True
    blocking_anomalies_count: int = 0
    blocking_anomalies: List[DispatchBlockingAnomaly] = Field(default_factory=list)


class DispatchStatusResponse(BaseModel):
    period: str
    compta: DispatchChannelStatus
    banque: DispatchChannelStatus


class DispatchComptaRequest(BaseModel):
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    format: Literal["csv", "xlsx"] = "csv"
    force_manual: bool = False


class DispatchBanqueRequest(BaseModel):
    period: str = Field(..., pattern=r"^\d{4}-\d{2}$")
    format: Literal["csv", "xlsx"] = "csv"
    execution_date: Optional[str] = None
    payment_label: Optional[str] = None


class DispatchFileDownload(BaseModel):
    export_id: str
    export_type: str
    filename: str
    download_url: str


class DispatchResultResponse(BaseModel):
    dispatch_id: str
    channel: DispatchChannel
    period: str
    status: DispatchStatus
    export_ids: List[str]
    files: List[ExportFileInfo] = Field(default_factory=list)
    downloads: List[DispatchFileDownload] = Field(default_factory=list)
    message: str
    transmission_id: Optional[str] = None
    transmission_status: Optional[str] = None
    transmission_provider: Optional[str] = None
    transmission_manual_fallback: bool = False


class MarkDispatchTransmittedRequest(BaseModel):
    note: Optional[str] = None


class MarkDispatchTransmittedResponse(BaseModel):
    dispatch_id: str
    status: DispatchStatus
    transmitted_at: datetime
    message: str


class DispatchHistoryEntry(BaseModel):
    id: str
    channel: DispatchChannel
    period: str
    status: DispatchStatus
    export_ids: List[str] = Field(default_factory=list)
    generated_at: datetime
    transmitted_at: Optional[datetime] = None
    transmission_note: Optional[str] = None
    created_by_name: Optional[str] = None


class DispatchHistoryResponse(BaseModel):
    dispatches: List[DispatchHistoryEntry]
    total: int


class DispatchScheduleUpsert(BaseModel):
    is_active: bool = True
    day_of_month: int = Field(5, ge=1, le=28)
    hour_utc: int = Field(6, ge=0, le=23)
    recipients: List[str] = Field(default_factory=list)


class DispatchScheduleOut(BaseModel):
    channel: DispatchChannel
    schedule_id: Optional[str] = None
    name: str
    export_type: str
    is_active: bool
    day_of_month: int
    hour_utc: int
    recipients: List[str] = Field(default_factory=list)
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None


class DispatchSchedulesResponse(BaseModel):
    schedules: List[DispatchScheduleOut]


class DispatchScheduleRunResponse(BaseModel):
    dispatch_id: Optional[str] = None
    export_id: Optional[str] = None
    message: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
