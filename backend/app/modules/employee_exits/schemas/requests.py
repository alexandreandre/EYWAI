"""
Schémas Pydantic entrée API du module employee_exits.

Migrés depuis schemas/employee_exit.py — comportement identique.
"""

from datetime import date
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# TYPES LITTÉRAUX (partagés avec responses)
# ============================================================================

ExitType = Literal[
    "demission",
    "rupture_conventionnelle",
    "licenciement",
    "depart_retraite",
    "fin_periode_essai",
]
ExitStatus = Literal[
    "demission_recue",
    "demission_preavis_en_cours",
    "demission_effective",
    "rupture_en_negociation",
    "rupture_validee",
    "rupture_homologuee",
    "rupture_effective",
    "licenciement_convocation",
    "licenciement_notifie",
    "licenciement_preavis_en_cours",
    "licenciement_effective",
    "archivee",
    "annulee",
]
DocumentType = Literal[
    "lettre_demission",
    "convention_rupture_signee",
    "lettre_licenciement",
    "accuse_reception",
    "convocation_entretien",
    "justificatif_autre",
    "certificat_travail",
    "attestation_pole_emploi",
    "solde_tout_compte",
    "recu_solde_compte",
    "attestation_portabilite_mutuelle",
]
NoticeIndemnityType = Literal["paid", "waived", "not_applicable"]
ChecklistCategory = Literal["administratif", "materiel", "acces", "legal", "autre"]
NotificationType = Literal[
    "status_change",
    "document_ready",
    "checklist_reminder",
    "exit_created",
    "exit_validated",
    "exit_archived",
]


# ============================================================================
# EMPLOYEE EXIT
# ============================================================================


class EmployeeExitCreate(BaseModel):
    """Schéma pour créer un nouveau processus de sortie"""

    employee_id: str
    exit_type: ExitType
    exit_request_date: date
    last_working_day: date
    exit_reason: Optional[str] = None
    notice_period_days: int = Field(default=0, ge=0)
    is_gross_misconduct: bool = False  # Faute grave
    notice_indemnity_type: NoticeIndemnityType = "paid"

    class Config:
        json_schema_extra = {
            "example": {
                "employee_id": "550e8400-e29b-41d4-a716-446655440000",
                "exit_type": "demission",
                "exit_request_date": "2025-01-15",
                "last_working_day": "2025-03-15",
                "exit_reason": "Nouvelle opportunité professionnelle",
                "notice_period_days": 60,
                "is_gross_misconduct": False,
                "notice_indemnity_type": "paid",
            }
        }


class EmployeeExitUpdate(BaseModel):
    """Schéma pour mettre à jour un processus de sortie"""

    status: Optional[ExitStatus] = None
    notice_start_date: Optional[date] = None
    notice_end_date: Optional[date] = None
    last_working_day: Optional[date] = None
    final_settlement_date: Optional[date] = None
    exit_reason: Optional[str] = None
    exit_notes: Optional[Dict[str, Any]] = None
    notice_period_days: Optional[int] = None
    is_gross_misconduct: Optional[bool] = None
    notice_indemnity_type: Optional[NoticeIndemnityType] = None


# ============================================================================
# EXIT DOCUMENTS
# ============================================================================


class ExitDocumentCreate(BaseModel):
    """Schéma pour créer/associer un document de sortie"""

    exit_id: str
    document_type: DocumentType
    storage_path: str
    filename: str
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    upload_notes: Optional[str] = None


class DocumentUploadUrlRequest(BaseModel):
    """Requête pour obtenir une URL signée d'upload"""

    filename: str
    document_type: DocumentType = "justificatif_autre"
    mime_type: Optional[str] = "application/pdf"


class ExitDocumentEditRequest(BaseModel):
    """Requête pour éditer un document de sortie"""

    document_data: Dict[str, Any]  # Données structurées du document
    changes_summary: str  # Résumé des modifications
    internal_note: Optional[str] = None  # Note interne (non visible dans le PDF)


# ============================================================================
# CHECKLIST
# ============================================================================


class ChecklistItemCreate(BaseModel):
    """Schéma pour créer un item de checklist"""

    exit_id: str
    item_code: str
    item_label: str
    item_description: Optional[str] = None
    item_category: ChecklistCategory = "autre"
    is_required: bool = True
    due_date: Optional[date] = None
    display_order: int = 0


class ChecklistItemUpdate(BaseModel):
    """Schéma pour mettre à jour un item de checklist"""

    is_completed: Optional[bool] = None
    completion_notes: Optional[str] = None
    due_date: Optional[date] = None


# ============================================================================
# STATUS UPDATE
# ============================================================================


class StatusUpdateRequest(BaseModel):
    """Requête pour changer le statut d'une sortie"""

    new_status: ExitStatus
    notes: Optional[str] = None


# ============================================================================
# PUBLISH DOCUMENTS
# ============================================================================


class PublishExitDocumentsRequest(BaseModel):
    """Requête pour publier des documents de sortie vers l'espace Documents du salarié"""

    document_ids: Optional[List[str]] = (
        None  # Si None, publie tous les documents générés
    )
    force_update: bool = False  # Si True, met à jour même si déjà publié


__all__ = [
    "ChecklistCategory",
    "ChecklistItemCreate",
    "ChecklistItemUpdate",
    "DocumentType",
    "DocumentUploadUrlRequest",
    "EmployeeExitCreate",
    "EmployeeExitUpdate",
    "ExitDocumentCreate",
    "ExitDocumentEditRequest",
    "ExitStatus",
    "ExitType",
    "NotificationType",
    "NoticeIndemnityType",
    "PublishExitDocumentsRequest",
    "StatusUpdateRequest",
]
