"""
DTOs du module residence_permits.

Définit les formes de données échangées dans la couche application (lecture seule).
La réponse publique reste ResidencePermitListItem (schemas.responses).
EnrichedResidencePermitRow / as_enriched_row : typage optionnel pour dict enrichi (non utilisé ailleurs pour l’instant).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict


class EnrichedResidencePermitRow(TypedDict, total=False):
    """
    Ligne employé enrichie avec le statut titre de séjour calculé.
    Correspond au dict retourné par enrich_row_with_residence_permit_status.
    """
    id: str
    first_name: str
    last_name: str
    is_subject_to_residence_permit: bool
    residence_permit_status: Optional[str]
    residence_permit_expiry_date: Optional[Any]  # date ou str selon source
    residence_permit_days_remaining: Optional[int]
    residence_permit_data_complete: Optional[bool]
    residence_permit_type: Optional[str]
    residence_permit_number: Optional[str]
    employment_status: str


def as_enriched_row(data: Dict[str, Any]) -> EnrichedResidencePermitRow:
    """Typage du dict enrichi pour usage dans la couche application."""
    return data  # type: ignore[return-value]
