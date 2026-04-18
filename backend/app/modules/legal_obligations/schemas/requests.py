"""Requêtes API obligations légales."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.modules.legal_obligations.schemas.responses import LegalObligationOverride


class LegalObligationOverrideWrite(BaseModel):
    """Corps PUT override (employee_id dans l’URL)."""

    criteria_training_completed: bool = False
    criteria_certification_obtained: bool = False
    criteria_career_evolution: bool = False
    notes: Optional[str] = None


def override_write_to_response(
    employee_id: str, body: LegalObligationOverrideWrite
) -> LegalObligationOverride:
    return LegalObligationOverride(
        employee_id=employee_id,
        criteria_training_completed=body.criteria_training_completed,
        criteria_certification_obtained=body.criteria_certification_obtained,
        criteria_career_evolution=body.criteria_career_evolution,
        notes=body.notes,
    )
