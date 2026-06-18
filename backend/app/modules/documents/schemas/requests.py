"""Requêtes API — documents générés."""

from __future__ import annotations

from datetime import date
from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field

DocumentStatus = Literal["brouillon", "envoye", "signe", "archive"]

DocumentCategory = Literal[
    "contrat",
    "avenant",
    "attestation_sortie",
    "attestation_situation",
    "attestation_courante",
]


class GenerateDocumentRequest(BaseModel):
    employee_id: str = Field(..., min_length=1)
    document_type: str = Field(..., min_length=1)
    category: DocumentCategory
    date_effet: Optional[date] = None
    motif: Optional[str] = None
    template_id: Optional[str] = None
    nouveau_salaire: Optional[float] = Field(
        None,
        description="Persisté dans generation_context pour rebouclage à la signature.",
    )
    ancien_salaire: Optional[float] = Field(
        None,
        description="Salaire avant modification (snapshot ou valeur front).",
    )
    ancien_poste: Optional[str] = None
    nouveau_poste: Optional[str] = None
    ancienne_duree: Optional[str] = None
    nouvelle_duree: Optional[str] = None
    ancien_lieu: Optional[str] = None
    nouveau_lieu: Optional[str] = None
    custom_fields: Optional[Dict[str, str]] = None
    recruitment_job_id: Optional[str] = None


class UpdateDocumentStatusRequest(BaseModel):
    status: DocumentStatus


class TransmitDocumentForm(BaseModel):
    """Champs formulaire (hors fichier) pour POST /api/documents/transmit."""

    employee_id: str = Field(..., min_length=1)
    document_label: str = Field(..., min_length=2, max_length=120)
    send_immediately: bool = True
