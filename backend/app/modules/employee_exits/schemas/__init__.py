"""
Schémas du module employee_exits.

Définitions locales (requests.py, responses.py). Compatibilité legacy :
les anciens imports depuis schemas.employee_exit restent valides via le fichier legacy.
"""
from app.modules.employee_exits.schemas.requests import (
    ChecklistCategory,
    ChecklistItemCreate,
    ChecklistItemUpdate,
    DocumentType,
    DocumentUploadUrlRequest,
    EmployeeExitCreate,
    EmployeeExitUpdate,
    ExitDocumentCreate,
    ExitDocumentEditRequest,
    ExitStatus,
    ExitType,
    NotificationType,
    NoticeIndemnityType,
    PublishExitDocumentsRequest,
    StatusUpdateRequest,
)
from app.modules.employee_exits.schemas.responses import (
    ChecklistItem,
    DocumentUploadUrlResponse,
    EmployeeExit,
    EmployeeExitWithDetails,
    ExitDocument,
    ExitDocumentDetails,
    ExitDocumentEditResponse,
    ExitIndemnityCalculation,
    ExitNotification,
    ExitNotificationCreate,
    ExitStatistics,
    IndemnityDetail,
    PublishExitDocumentsResponse,
    PublishedDocumentStatus,
    SimpleEmployee,
    StatusTransitionResponse,
)

__all__ = [
    # Types
    "ChecklistCategory",
    "DocumentType",
    "ExitStatus",
    "ExitType",
    "NotificationType",
    "NoticeIndemnityType",
    # Requests
    "ChecklistItemCreate",
    "ChecklistItemUpdate",
    "DocumentUploadUrlRequest",
    "EmployeeExitCreate",
    "EmployeeExitUpdate",
    "ExitDocumentCreate",
    "ExitDocumentEditRequest",
    "PublishExitDocumentsRequest",
    "StatusUpdateRequest",
    # Responses
    "ChecklistItem",
    "DocumentUploadUrlResponse",
    "EmployeeExit",
    "EmployeeExitWithDetails",
    "ExitDocument",
    "ExitDocumentDetails",
    "ExitDocumentEditResponse",
    "ExitIndemnityCalculation",
    "ExitNotification",
    "ExitNotificationCreate",
    "ExitStatistics",
    "IndemnityDetail",
    "PublishExitDocumentsResponse",
    "PublishedDocumentStatus",
    "SimpleEmployee",
    "StatusTransitionResponse",
]
