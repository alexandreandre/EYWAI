"""
Schémas du module payslips.

Ré-export pour usage dans le router et l'application.
ContractResponse (URL signée) reste dans app.shared.schemas (utilisé par employees).
"""

from app.modules.payslips.schemas.requests import (
    InternalNoteCreate,
    PayslipEditRequest,
    PayslipRequest,
    PayslipRestoreRequest,
)
from app.modules.payslips.schemas.responses import (
    HistoryEntry,
    InternalNote,
    PayslipDetail,
    PayslipEditResponse,
    PayslipInfo,
    PayslipRestoreResponse,
)

__all__ = [
    "PayslipRequest",
    "PayslipEditRequest",
    "PayslipRestoreRequest",
    "InternalNoteCreate",
    "PayslipInfo",
    "PayslipDetail",
    "PayslipEditResponse",
    "PayslipRestoreResponse",
    "HistoryEntry",
    "InternalNote",
]
