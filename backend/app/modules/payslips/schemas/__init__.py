"""
Schémas du module payslips.

Ré-export pour usage dans le router et l'application.
ContractResponse (URL signée) reste dans app.shared.schemas (utilisé par employees).
"""

from app.modules.payslips.schemas.requests import (
    AcquitAlertRequest,
    InternalNoteCreate,
    PayslipEditRequest,
    PayslipPreviewRequest,
    PayslipRequest,
    PayslipRestoreRequest,
)
from app.modules.payslips.schemas.responses import (
    ComparisonLineResponse,
    ComparisonResultResponse,
    HistoryEntry,
    InternalNote,
    PayslipAlertResponse,
    PayslipDetail,
    PayslipEditResponse,
    PayslipInfo,
    PayslipPreviewResponse,
    PayslipRestoreResponse,
    TrendMonthResponse,
    TrendResponse,
)

__all__ = [
    "PayslipRequest",
    "PayslipEditRequest",
    "PayslipRestoreRequest",
    "AcquitAlertRequest",
    "InternalNoteCreate",
    "PayslipInfo",
    "PayslipDetail",
    "PayslipEditResponse",
    "PayslipPreviewRequest",
    "PayslipPreviewResponse",
    "PayslipRestoreResponse",
    "HistoryEntry",
    "InternalNote",
    "PayslipAlertResponse",
    "ComparisonLineResponse",
    "ComparisonResultResponse",
    "TrendMonthResponse",
    "TrendResponse",
]
