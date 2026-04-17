"""Lecture statuts obligations légales."""

from __future__ import annotations

from typing import List, Optional

from app.modules.legal_obligations.infrastructure.repository import legal_obligations_repository
from app.modules.legal_obligations.schemas.responses import (
    LegalObligationStatus,
    OverdueCountResponse,
)


def _row_to_status(row: dict) -> LegalObligationStatus:
    return LegalObligationStatus(
        employee_id=str(row["employee_id"]),
        employee_name=str(row["employee_name"]),
        hire_date=row.get("hire_date"),
        last_professional_interview_date=row.get("last_professional_interview_date"),
        professional_interview_status=row["professional_interview_status"],
        professional_interview_next_due=row.get("professional_interview_next_due"),
        six_year_review_status=row["six_year_review_status"],
        six_year_criteria_met=bool(row.get("six_year_criteria_met")),
        six_year_next_due=row.get("six_year_next_due"),
        last_six_year_review_date=row.get("last_six_year_review_date"),
        criteria_training_completed=bool(row.get("criteria_training_completed")),
        criteria_certification_obtained=bool(row.get("criteria_certification_obtained")),
        criteria_career_evolution=bool(row.get("criteria_career_evolution")),
    )


def get_all_status(
    company_id: str, status_filter: Optional[str] = None
) -> List[LegalObligationStatus]:
    rows = legal_obligations_repository.get_all_employees_status(company_id)
    out = [_row_to_status(r) for r in rows]
    if status_filter in ("overdue", "due_soon", "up_to_date"):
        out = [r for r in out if r.professional_interview_status == status_filter]
    return out


def get_employee_status(company_id: str, employee_id: str) -> LegalObligationStatus:
    row = legal_obligations_repository.get_employee_status(company_id, employee_id)
    if not row:
        raise LookupError("Employé non trouvé ou inactif.")
    return _row_to_status(row)


def get_overdue_count(company_id: str) -> OverdueCountResponse:
    n = legal_obligations_repository.get_overdue_count(company_id)
    return OverdueCountResponse(count=n)
