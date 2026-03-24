"""
Schémas de réponse du module residence_permits.

Source unique pour ResidencePermitListItem (anciennement défini dans api/routers/residence_permits.py).
Comportement identique ; le router legacy pourra importer d'ici lors du basculement.
"""
from typing import Optional

from pydantic import BaseModel


class ResidencePermitListItem(BaseModel):
    """Un item de la liste pour la page Titres de séjour."""

    employee_id: str
    first_name: str
    last_name: str
    is_subject_to_residence_permit: bool
    residence_permit_status: Optional[str] = None  # "valid" | "to_renew" | "expired" | "to_complete"
    residence_permit_expiry_date: Optional[str] = None
    residence_permit_days_remaining: Optional[int] = None
    residence_permit_data_complete: Optional[bool] = None
    residence_permit_type: Optional[str] = None
    residence_permit_number: Optional[str] = None
