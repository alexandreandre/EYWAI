"""
Schémas Pydantic sortie API du module employee_exits.

Migrés depuis schemas/employee_exit.py — comportement identique.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel

from app.modules.employee_exits.schemas.requests import (
    ChecklistCategory,
    DocumentType,
    ExitStatus,
    ExitType,
    NotificationType,
)


# ============================================================================
# EMPLOYEE EXIT
# ============================================================================


class EmployeeExit(BaseModel):
    """Schéma complet d'un processus de sortie"""

    id: str
    company_id: str
    employee_id: str

    # Type et statut
    exit_type: ExitType
    status: ExitStatus

    # Dates
    exit_request_date: Optional[date] = None
    notice_start_date: Optional[date] = None
    notice_end_date: Optional[date] = None
    last_working_day: Optional[date] = None
    final_settlement_date: Optional[date] = None

    # Préavis
    notice_period_days: Optional[int] = None
    is_gross_misconduct: Optional[bool] = None
    notice_indemnity_type: Optional[str] = None

    # Détails
    exit_reason: Optional[str] = None
    exit_notes: Optional[Dict[str, Any]] = None

    # Calculs
    calculated_indemnities: Optional[Dict[str, Any]] = None
    remaining_vacation_days: Optional[float] = None
    final_net_amount: Optional[float] = None

    # Workflow
    initiated_by: Optional[str] = None
    validated_by: Optional[str] = None
    validation_date: Optional[datetime] = None
    archived_by: Optional[str] = None
    archived_at: Optional[datetime] = None

    # Métadonnées
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SimpleEmployee(BaseModel):
    """Informations simplifiées d'un employé pour les réponses enrichies"""

    id: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    job_title: Optional[str] = None


class EmployeeExitWithDetails(EmployeeExit):
    """Sortie avec détails employé, documents et checklist"""

    employee: Optional[Dict[str, Any]] = None
    documents: List[Dict[str, Any]] = []
    checklist_items: List[Dict[str, Any]] = []
    checklist_completion_rate: float = 0.0


# ============================================================================
# EXIT DOCUMENTS
# ============================================================================


class DocumentUploadUrlResponse(BaseModel):
    """Réponse avec URL signée pour upload"""

    upload_url: str
    storage_path: str
    expires_in: int = 3600  # 1 heure


class ExitDocument(BaseModel):
    """Schéma complet d'un document de sortie"""

    id: str
    exit_id: str
    company_id: str

    # Classification
    document_type: DocumentType
    document_category: Literal["uploaded", "generated"]

    # Stockage
    storage_path: str
    filename: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None

    # Génération (pour documents auto-générés)
    generation_template: Optional[str] = None
    generation_data: Optional[Dict[str, Any]] = None
    generated_at: Optional[datetime] = None

    # Upload
    uploaded_by: Optional[str] = None
    upload_notes: Optional[str] = None

    # Statut
    is_signed: bool = False
    signature_date: Optional[date] = None
    is_transmitted: bool = False
    transmission_date: Optional[date] = None

    # Publication vers l'espace salarié
    published_to_employee: bool = False
    published_at: Optional[datetime] = None
    published_by: Optional[str] = None

    # Métadonnées
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # URL de téléchargement (ajoutée dynamiquement, non en base)
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


class ExitDocumentEditResponse(BaseModel):
    """Réponse après édition d'un document"""

    success: bool
    message: str
    document_id: str
    version: int
    edited_at: datetime


class ExitDocumentDetails(ExitDocument):
    """Détails complets d'un document avec données éditables"""

    document_data: Optional[Dict[str, Any]] = None  # Structure éditable du document
    edit_history: Optional[List[Dict[str, Any]]] = None  # Historique des modifications
    version: int = 1
    manually_edited: bool = False
    last_edited_by: Optional[str] = None
    last_edited_at: Optional[datetime] = None


# ============================================================================
# CHECKLIST
# ============================================================================


class ChecklistItem(BaseModel):
    """Schéma complet d'un item de checklist"""

    id: str
    exit_id: str
    company_id: str

    # Détails
    item_code: str
    item_label: str
    item_description: Optional[str] = None
    item_category: ChecklistCategory

    # Statut
    is_completed: bool
    completed_by: Optional[str] = None
    completed_at: Optional[datetime] = None
    completion_notes: Optional[str] = None

    # Configuration
    is_required: Optional[bool] = None
    due_date: Optional[date] = None
    display_order: Optional[int] = None

    # Métadonnées
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============================================================================
# INDEMNITIES
# ============================================================================


class IndemnityDetail(BaseModel):
    """Détail d'une indemnité calculée"""

    montant: Optional[float] = None
    description: Optional[str] = None
    calcul: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ExitIndemnityCalculation(BaseModel):
    """Résultat du calcul des indemnités de sortie"""

    exit_id: Optional[str] = None
    employee_id: Optional[str] = None

    # Ancienneté
    anciennete_annees: Optional[float] = None
    salaire_reference: Optional[float] = None

    # Indemnités détaillées
    indemnite_preavis: Optional[IndemnityDetail] = None
    indemnite_conges: Optional[IndemnityDetail] = None
    indemnite_licenciement: Optional[IndemnityDetail] = None
    indemnite_rupture_conventionnelle: Optional[IndemnityDetail] = None

    # Totaux
    total_gross_indemnities: float
    total_net_indemnities: float

    # Métadonnées du calcul
    calculation_date: Optional[datetime] = None
    calculation_details: Dict[str, Any] = {}


# ============================================================================
# NOTIFICATIONS
# ============================================================================


class ExitNotificationCreate(BaseModel):
    """Schéma pour créer une notification"""

    exit_id: str
    notification_type: NotificationType
    recipient_id: Optional[str] = None
    recipient_email: Optional[str] = None
    subject: str
    message_body: str


class ExitNotification(BaseModel):
    """Schéma complet d'une notification"""

    id: str
    exit_id: str
    company_id: str

    # Détails
    notification_type: NotificationType
    recipient_id: Optional[str] = None
    recipient_email: Optional[str] = None

    # Contenu
    subject: Optional[str] = None
    message_body: Optional[str] = None

    # Statut
    status: Literal["pending", "sent", "failed"]
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Métadonnées
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# STATUS UPDATE
# ============================================================================


class StatusTransitionResponse(BaseModel):
    """Réponse d'un changement de statut"""

    success: bool
    exit: EmployeeExit
    message: Optional[str] = None


# ============================================================================
# STATISTICS
# ============================================================================


class ExitStatistics(BaseModel):
    """Statistiques sur les sorties"""

    total_exits: int
    by_type: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    average_notice_period: float = 0.0
    average_indemnity: float = 0.0


# ============================================================================
# PUBLISH DOCUMENTS
# ============================================================================


class PublishedDocumentStatus(BaseModel):
    """Statut de publication d'un document"""

    exit_document_id: str
    document_type: str
    filename: str
    status: Literal[
        "published", "updated", "already_published", "failed", "file_missing"
    ]
    employee_document_id: Optional[str] = None
    url: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None


class PublishExitDocumentsResponse(BaseModel):
    """Réponse de la publication de documents"""

    exit_id: str
    employee_id: str
    success: bool
    documents: List[PublishedDocumentStatus]
    total_published: int
    total_updated: int
    total_failed: int
    total_already_published: int


__all__ = [
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
