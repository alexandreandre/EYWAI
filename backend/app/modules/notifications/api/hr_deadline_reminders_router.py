"""Routes /api/hr-deadline-reminders — relances échéances RH."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.modules.notifications.application.hr_deadline_reminders import (
    fetch_employees_for_hr_deadline_reminders,
    send_hr_deadline_reminders,
)
from app.modules.employees.domain.deadline_reminders import list_hr_deadline_candidates
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/hr-deadline-reminders", tags=["HR Deadline Reminders"])


def _company_id_rh(current_user: User = Depends(get_current_user)) -> str:
    cid = current_user.active_company_id
    if not cid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucune entreprise active",
        )
    if not current_user.is_platform_admin and not current_user.has_rh_access_in_company(
        str(cid)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès RH requis pour cette entreprise",
        )
    return str(cid)


@router.get("/candidates")
def list_hr_deadline_candidates_endpoint(
    company_id: str = Depends(_company_id_rh),
):
    """Salariés avec échéance CDD, période d'essai ou titre de séjour dans les fenêtres de relance."""
    employees = fetch_employees_for_hr_deadline_reminders(company_id)
    candidates = list_hr_deadline_candidates(employees)
    return [
        {
            "employee_id": c.employee_id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "reminder_type": c.reminder_type,
            "deadline": c.deadline.isoformat(),
            "days_remaining": c.days_remaining,
            "label": c.label,
        }
        for c in candidates
    ]


@router.post("/send")
def send_hr_deadline_reminders_endpoint(
    company_id: str = Depends(_company_id_rh),
):
    """Envoie les relances e-mail RH pour les échéances CDD, PE et titres de séjour."""
    result = send_hr_deadline_reminders(company_id)
    sent = int(result.get("sent", 0))
    message = (
        f"{sent} relance(s) enregistrée(s)"
        if sent
        else "Aucune nouvelle relance à envoyer"
    )
    return {**result, "message": message}
