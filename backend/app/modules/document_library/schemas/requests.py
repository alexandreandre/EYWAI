"""Schémas de requête — bibliothèque de modèles documents."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "cdi": "CDI",
    "cdd": "CDD",
    "convention_stage": "Convention de stage",
    "contrat_alternance": "Contrat d'alternance",
    "avenant_salaire": "Avenant - Modification de salaire",
    "avenant_poste": "Avenant - Changement de poste",
    "avenant_temps": "Avenant - Modification du temps de travail",
    "avenant_lieu": "Avenant - Changement de lieu de travail",
    "avenant_general": "Avenant - Modification générale",
    "attestation_emploi": "Attestation d'emploi",
    "attestation_presence": "Attestation de présence",
    "attestation_anciennete": "Attestation d'ancienneté",
    "attestation_poste": "Attestation de poste",
    "attestation_salaire": "Attestation de salaire",
    "attestation_revenus": "Attestation de revenus annuels",
    "attestation_location": "Attestation employeur pour location",
    "attestation_pret": "Attestation pour prêt bancaire",
    "attestation_retraite": "Attestation retraite",
    "document_transmis": "Document transmis",
}

KNOWN_DOCUMENT_TYPES: frozenset[str] = frozenset(DOCUMENT_TYPE_LABELS.keys())

DocumentTemplateStatus = Literal["active", "archived"]


class DocumentTemplateCreate(BaseModel):
    document_type: str = Field(..., min_length=1)
    name: Optional[str] = None


class DocumentTemplateUpdate(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None
    status: Optional[DocumentTemplateStatus] = None
