"""
Entités du domaine absences.

Alignées sur la table absence_requests et les schémas du module (schemas/responses.AbsenceRequest).
Pas de dépendance DB ni FastAPI.
"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional


@dataclass
class AbsenceRequestEntity:
    """
    Demande d'absence (agrégat racine).
    Source : table absence_requests, schémas du module absences.
    """
    id: str
    employee_id: str
    company_id: Optional[str]
    type: str  # AbsenceType
    selected_days: List[date]
    status: str  # AbsenceStatus
    comment: Optional[str] = None
    manager_id: Optional[str] = None
    attachment_url: Optional[str] = None
    filename: Optional[str] = None
    event_subtype: Optional[str] = None
    jours_payes: Optional[int] = None
    created_at: Optional[datetime] = None
