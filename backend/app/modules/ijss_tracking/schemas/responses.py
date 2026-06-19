"""Schémas sortie API suivi IJSS."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class IjssPeriodSummary(BaseModel):
    ok: int = 0
    variance: int = 0
    pending: int = 0


class IjssDashboardRow(BaseModel):
    expected_line_id: Optional[str] = None
    employee_id: str
    employee_name: str
    absence_request_id: Optional[str] = None
    ijss_theorique: float = 0
    ijss_subrogees_bulletin: float = 0
    received_cpam: float = 0
    received_bank: float = 0
    line_status: str = "pending"
    subrogation_active: bool = True
    ijss_brut_validated: Optional[float] = None
    validation_source: Optional[str] = None
    applied_to_payslip_at: Optional[str] = None
    applied_ijss_brut: Optional[float] = None


class IjssUnmatchedReceivedLine(BaseModel):
    id: str
    source: str
    amount: float = 0
    employee_name_raw: Optional[str] = None
    employee_nir: Optional[str] = None
    payment_date: Optional[str] = None


class IjssPeriodDashboard(BaseModel):
    period: Dict[str, Any]
    summary: IjssPeriodSummary
    rows: List[IjssDashboardRow]
    unmatched_received: List[IjssUnmatchedReceivedLine] = []


class IjssAbsenceStatus(BaseModel):
    status: str
    absence_request_id: str
    expected_line_id: Optional[str] = None
    ijss_subrogees_bulletin: float = 0
    ijss_brut_validated: Optional[float] = None
    applied_to_payslip_at: Optional[str] = None
    applied_ijss_brut: Optional[float] = None


class IjssImportPreviewResponse(BaseModel):
    batch_id: str
    preview: Dict[str, Any]
    items_preview: List[Dict[str, Any]]
    detected_mapping: Optional[Dict[str, str]] = None
