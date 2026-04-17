"""Commandes obligations légales (overrides RH)."""

from __future__ import annotations

from typing import Any, Dict

from app.modules.legal_obligations.infrastructure.repository import legal_obligations_repository
from app.modules.legal_obligations.schemas.requests import (
    LegalObligationOverrideWrite,
    override_write_to_response,
)
from app.modules.legal_obligations.schemas.responses import LegalObligationOverride


def save_override(
    company_id: str,
    employee_id: str,
    body: LegalObligationOverrideWrite,
    updated_by: str,
) -> LegalObligationOverride:
    emp = legal_obligations_repository.get_employee_row(company_id, employee_id)
    if not emp:
        raise LookupError("Employé non trouvé.")
    payload: Dict[str, Any] = {
        "criteria_training_completed": body.criteria_training_completed,
        "criteria_certification_obtained": body.criteria_certification_obtained,
        "criteria_career_evolution": body.criteria_career_evolution,
        "notes": body.notes,
        "updated_by": updated_by,
    }
    legal_obligations_repository.upsert_override(company_id, employee_id, payload)
    return override_write_to_response(employee_id, body)
