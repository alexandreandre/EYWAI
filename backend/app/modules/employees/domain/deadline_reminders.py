"""Règles pures : relances RH fin CDD, période d'essai et titre de séjour."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

from app.modules.employees.domain.trial_period_shared import (
    TRIAL_REMINDER_DAYS,
    compute_trial_period_end,
    parse_date,
)

CDD_REMINDER_DAYS = 15
RESIDENCE_REMINDER_DAYS = 30

REMINDER_TYPE_CDD = "cdd_end"
REMINDER_TYPE_TRIAL = "trial_end"
REMINDER_TYPE_RESIDENCE = "residence_permit"

REMINDER_TYPE_LABELS: Dict[str, str] = {
    REMINDER_TYPE_CDD: "Fin de CDD",
    REMINDER_TYPE_TRIAL: "Fin de période d'essai",
    REMINDER_TYPE_RESIDENCE: "Expiration titre de séjour",
}


@dataclass(frozen=True)
class DeadlineCandidate:
    employee_id: str
    reminder_type: str
    deadline: date
    days_remaining: int
    label: str
    first_name: str
    last_name: str


def is_active_for_reminder(employment_status: Any) -> bool:
    return str(employment_status or "actif").strip().lower() == "actif"


def days_until(deadline: date, reference_date: date) -> int:
    return (deadline - reference_date).days


def is_in_reminder_window(
    deadline: date,
    max_days: int,
    reference_date: date,
) -> bool:
    remaining = days_until(deadline, reference_date)
    return 0 <= remaining <= max_days


def _employee_name(emp: Dict[str, Any]) -> tuple[str, str]:
    return (
        str(emp.get("first_name") or "").strip(),
        str(emp.get("last_name") or "").strip(),
    )


def _format_deadline_label(reminder_type: str, deadline: date) -> str:
    type_label = REMINDER_TYPE_LABELS.get(reminder_type, reminder_type)
    return f"{type_label} le {deadline.strftime('%d/%m/%Y')}"


def _cdd_deadline(emp: Dict[str, Any]) -> Optional[date]:
    ctype = str(emp.get("contract_type") or "").upper()
    if "CDD" not in ctype:
        return None
    return parse_date(emp.get("contract_end_date"))


def _trial_deadline(emp: Dict[str, Any]) -> Optional[date]:
    """Fin de la période d'essai active, jointe depuis la table trial_periods."""
    trial = emp.get("trial_period")
    if not isinstance(trial, dict):
        return None
    if str(trial.get("status") or "") != "en_cours":
        return None
    return parse_date(trial.get("end_date"))


def _residence_deadline(emp: Dict[str, Any]) -> Optional[date]:
    if not emp.get("is_subject_to_residence_permit"):
        return None
    return parse_date(emp.get("residence_permit_expiry_date"))


def _iter_candidates_for_employee(
    emp: Dict[str, Any],
    reference_date: date,
) -> List[DeadlineCandidate]:
    if not is_active_for_reminder(emp.get("employment_status")):
        return []

    employee_id = str(emp.get("id") or "").strip()
    if not employee_id:
        return []

    first_name, last_name = _employee_name(emp)
    out: List[DeadlineCandidate] = []

    checks = (
        (REMINDER_TYPE_CDD, _cdd_deadline(emp), CDD_REMINDER_DAYS),
        (REMINDER_TYPE_TRIAL, _trial_deadline(emp), TRIAL_REMINDER_DAYS),
        (REMINDER_TYPE_RESIDENCE, _residence_deadline(emp), RESIDENCE_REMINDER_DAYS),
    )
    for reminder_type, deadline, max_days in checks:
        if deadline is None:
            continue
        if not is_in_reminder_window(deadline, max_days, reference_date):
            continue
        remaining = days_until(deadline, reference_date)
        out.append(
            DeadlineCandidate(
                employee_id=employee_id,
                reminder_type=reminder_type,
                deadline=deadline,
                days_remaining=remaining,
                label=_format_deadline_label(reminder_type, deadline),
                first_name=first_name,
                last_name=last_name,
            )
        )
    return out


def list_hr_deadline_candidates(
    employees: List[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> List[DeadlineCandidate]:
    ref = reference_date or date.today()
    candidates: List[DeadlineCandidate] = []
    for emp in employees:
        candidates.extend(_iter_candidates_for_employee(emp, ref))
    return candidates


def count_expiring_cdds(
    employees: List[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> int:
    ref = reference_date or date.today()
    count = 0
    for emp in employees:
        if not is_active_for_reminder(emp.get("employment_status")):
            continue
        deadline = _cdd_deadline(emp)
        if deadline and is_in_reminder_window(deadline, CDD_REMINDER_DAYS, ref):
            count += 1
    return count


def count_ending_trial_periods(
    employees: List[Dict[str, Any]],
    reference_date: Optional[date] = None,
) -> int:
    ref = reference_date or date.today()
    count = 0
    for emp in employees:
        if not is_active_for_reminder(emp.get("employment_status")):
            continue
        deadline = _trial_deadline(emp)
        if deadline and is_in_reminder_window(deadline, TRIAL_REMINDER_DAYS, ref):
            count += 1
    return count
