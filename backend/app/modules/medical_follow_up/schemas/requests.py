# app/modules/medical_follow_up/schemas/requests.py
"""Schémas de requête pour le module suivi médical (comportement identique au legacy)."""

from typing import Optional

from pydantic import BaseModel


class MarkPlanifiedBody(BaseModel):
    """Corps pour PATCH .../obligations/{id}/planified."""

    planned_date: str
    justification: Optional[str] = None


class MarkCompletedBody(BaseModel):
    """Corps pour PATCH .../obligations/{id}/completed."""

    completed_date: str
    justification: Optional[str] = None


class CreateOnDemandBody(BaseModel):
    """Corps pour POST .../obligations/on-demand."""

    employee_id: str
    request_motif: str
    request_date: str
