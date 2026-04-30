"""Requêtes API — documents générés."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

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


class UpdateDocumentStatusRequest(BaseModel):
    status: DocumentStatus
