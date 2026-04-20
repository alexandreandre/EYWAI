"""Schémas de réponse — widget Signatures en attente."""

from typing import List, Optional

from pydantic import BaseModel, Field


class PendingSignatureItem(BaseModel):
    id: str
    document_name: str
    employee_id: str
    employee_first_name: Optional[str] = None
    employee_last_name: Optional[str] = None
    yousign_procedure_id: Optional[str] = None
    signature_status: str
    sent_at: Optional[str] = None
    expires_at: Optional[str] = None
    days_until_expiry: Optional[int] = None
    is_urgent: bool
    last_reminder_at: Optional[str] = None
    days_since_reminder: Optional[int] = None
    created_at: str


class PendingSignaturesResponse(BaseModel):
    """Réponse widget : vue RH (yousign_configured renseigné) ou employé (champ omis / null)."""

    yousign_configured: Optional[bool] = Field(
        default=None,
        description="True/False pour la vue RH ; None pour la vue employé.",
    )
    total: int
    items: List[PendingSignatureItem]
