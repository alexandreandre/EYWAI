# app/modules/medical_follow_up/domain/entities.py
"""Entités du domaine suivi médical (placeholder pour migration)."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MedicalObligation:
    """
    Obligation de visite médicale (VIP, SIR, reprise, mi-carrière, demande).
    Structure cible ; le mapping depuis la persistance sera dans infrastructure.
    """

    id: str
    company_id: str
    employee_id: str
    visit_type: str
    trigger_type: str
    due_date: str
    priority: int
    status: str
    rule_source: str
    justification: Optional[str] = None
    planned_date: Optional[str] = None
    completed_date: Optional[str] = None
    collective_agreement_idcc: Optional[str] = None
    request_motif: Optional[str] = None
    request_date: Optional[str] = None
