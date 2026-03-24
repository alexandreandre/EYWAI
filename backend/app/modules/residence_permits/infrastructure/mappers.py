"""
Mappers residence_permits : dict enrichi -> forme pour ResidencePermitListItem.

Pas de table dédiée ; mapping depuis les champs employé + résultat du calcul de statut.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

# Import du schéma pour la construction (évite duplication des clés)
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem


def _normalize_expiry_date(val: Any) -> Optional[str]:
    """Le calculateur legacy peut renvoyer date ou str ; le schéma attend str | None."""
    if val is None:
        return None
    if isinstance(val, date):
        return val.isoformat()
    return str(val) if val else None


def enriched_row_to_list_item(enriched: Dict[str, Any]) -> ResidencePermitListItem:
    """
    Construit un ResidencePermitListItem à partir d'un dict employé déjà enrichi
    par le calculateur de statut (id -> employee_id, champs statut présents).
    """
    return ResidencePermitListItem(
        employee_id=str(enriched.get("id", "")),
        first_name=enriched.get("first_name", ""),
        last_name=enriched.get("last_name", ""),
        is_subject_to_residence_permit=enriched.get("is_subject_to_residence_permit", True),
        residence_permit_status=enriched.get("residence_permit_status"),
        residence_permit_expiry_date=_normalize_expiry_date(enriched.get("residence_permit_expiry_date")),
        residence_permit_days_remaining=enriched.get("residence_permit_days_remaining"),
        residence_permit_data_complete=enriched.get("residence_permit_data_complete"),
        residence_permit_type=enriched.get("residence_permit_type"),
        residence_permit_number=enriched.get("residence_permit_number"),
    )
