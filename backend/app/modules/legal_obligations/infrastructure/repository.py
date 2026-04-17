"""
Repository obligations légales (employés, annual_reviews, legal_obligation_overrides).
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase

from app.modules.legal_obligations.domain.interfaces import AbstractLegalObligationsRepository

COMPLETED_REVIEW_STATUSES = frozenset({"cloture", "realise"})
INTERVIEW_PROFESSIONAL = "professional_2ans"
INTERVIEW_SIX_YEAR = "competency_6ans"


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val)[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _add_calendar_years(d: date, years: int) -> date:
    y = d.year + years
    m = d.month
    last = calendar.monthrange(y, m)[1]
    return date(y, m, min(d.day, last))


def _review_effective_date(row: Dict[str, Any]) -> Optional[date]:
    return _parse_date(row.get("completed_date")) or _parse_date(row.get("planned_date"))


def _is_active_employee(row: Dict[str, Any]) -> bool:
    st = row.get("employment_status")
    if st is None:
        return True
    if st in ("parti", "en_sortie"):
        return False
    return st == "actif"


def _employee_display_name(row: Dict[str, Any]) -> str:
    fn = str(row.get("first_name") or "").strip()
    ln = str(row.get("last_name") or "").strip()
    return f"{fn} {ln}".strip() or "Collaborateur"


def _professional_status(
    hire_date: Optional[date],
    last_prof_date: Optional[date],
    today: date,
) -> Tuple[str, Optional[date], Optional[date]]:
    """
    Retourne (status, last_prof_date, next_due).
    date_ref = dernier entretien pro complété, sinon hire_date.
    """
    date_ref: Optional[date] = None
    if last_prof_date is not None:
        date_ref = last_prof_date
    elif hire_date is not None:
        date_ref = hire_date

    if date_ref is None:
        return "unknown", last_prof_date, None

    next_due = _add_calendar_years(date_ref, 2)
    horizon = today + timedelta(days=90)

    if next_due < today:
        return "overdue", last_prof_date, next_due
    if today <= next_due <= horizon:
        return "due_soon", last_prof_date, next_due
    return "up_to_date", last_prof_date, next_due


def _six_year_block(
    hire_date: Optional[date],
    reviews: List[Dict[str, Any]],
    override: Optional[Dict[str, Any]],
    today: date,
) -> Tuple[str, bool, Optional[date], Optional[date], bool, bool, bool]:
    """
    Retourne (
      six_year_review_status,
      six_year_criteria_met,
      six_year_next_due,
      last_six_year_review_date,
      crit_train, crit_cert, crit_career,
    )
    """
    if hire_date is None:
        return "unknown", False, None, None, False, False, False

    six_due = _add_calendar_years(hire_date, 6)

    last_six: Optional[date] = None
    auto_train = False
    for row in reviews:
        if str(row.get("interview_type") or "") != INTERVIEW_SIX_YEAR:
            continue
        if str(row.get("status") or "") not in COMPLETED_REVIEW_STATUSES:
            continue
        ed = _review_effective_date(row)
        if ed is None:
            continue
        if hire_date <= ed <= six_due:
            auto_train = True
        if last_six is None or ed > last_six:
            last_six = ed

    o_train = bool(override.get("criteria_training_completed")) if override else False
    o_cert = bool(override.get("criteria_certification_obtained")) if override else False
    o_career = bool(override.get("criteria_career_evolution")) if override else False

    crit_train = auto_train or o_train
    crit_cert = o_cert
    crit_career = o_career
    criteria_met = crit_train or crit_cert or crit_career

    if today < six_due:
        status = "in_progress"
    elif criteria_met:
        status = "validated"
    else:
        status = "not_validated"

    return status, criteria_met, six_due, last_six, crit_train, crit_cert, o_career


def _compute_status_for_employee(
    emp: Dict[str, Any],
    reviews: List[Dict[str, Any]],
    override: Optional[Dict[str, Any]],
    today: date,
) -> Dict[str, Any]:
    hire_date = _parse_date(emp.get("hire_date"))
    eid = str(emp["id"])

    last_prof: Optional[date] = None
    for row in reviews:
        if str(row.get("employee_id")) != eid:
            continue
        if str(row.get("interview_type") or "") != INTERVIEW_PROFESSIONAL:
            continue
        if str(row.get("status") or "") not in COMPLETED_REVIEW_STATUSES:
            continue
        ed = _review_effective_date(row)
        if ed is None:
            continue
        if last_prof is None or ed > last_prof:
            last_prof = ed

    prof_st, last_prof_out, next_prof = _professional_status(hire_date, last_prof, today)

    six_st, six_met, six_next, last_six, c_train, c_cert, c_career = _six_year_block(
        hire_date, reviews, override, today
    )

    return {
        "employee_id": eid,
        "employee_name": _employee_display_name(emp),
        "hire_date": hire_date,
        "last_professional_interview_date": last_prof_out,
        "professional_interview_status": prof_st,
        "professional_interview_next_due": next_prof,
        "six_year_review_status": six_st,
        "six_year_criteria_met": six_met,
        "six_year_next_due": six_next,
        "last_six_year_review_date": last_six,
        "criteria_training_completed": c_train,
        "criteria_certification_obtained": c_cert,
        "criteria_career_evolution": c_career,
    }


class SupabaseLegalObligationsRepository(AbstractLegalObligationsRepository):
    """Implémentation Supabase."""

    def get_employee_id_for_user(self, user_id: str, company_id: str) -> Optional[str]:
        r = (
            supabase.table("employees")
            .select("id")
            .eq("user_id", user_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return str(r.data["id"]) if r and r.data else None

    def get_active_employees(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, first_name, last_name, hire_date, user_id, employment_status")
            .eq("company_id", company_id)
            .order("last_name")
            .execute()
        )
        rows = [dict(x) for x in list(r.data or []) if r]
        return [row for row in rows if _is_active_employee(row)]

    def get_employee_row(self, company_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, first_name, last_name, hire_date, user_id, employment_status")
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return None
        return dict(r.data)

    def get_completed_reviews_for_company(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("annual_reviews")
            .select(
                "id, employee_id, company_id, interview_type, status, "
                "planned_date, completed_date, created_at"
            )
            .eq("company_id", company_id)
            .in_("status", list(COMPLETED_REVIEW_STATUSES))
            .execute()
        )
        return [dict(x) for x in list(r.data or []) if r]

    def get_overrides_for_company(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("legal_obligation_overrides")
            .select("*")
            .eq("company_id", company_id)
            .execute()
        )
        return [dict(x) for x in list(r.data or []) if r]

    def upsert_override(
        self,
        company_id: str,
        employee_id: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            "company_id": company_id,
            "employee_id": employee_id,
            "criteria_training_completed": bool(data.get("criteria_training_completed")),
            "criteria_certification_obtained": bool(data.get("criteria_certification_obtained")),
            "criteria_career_evolution": bool(data.get("criteria_career_evolution")),
            "notes": data.get("notes"),
            "updated_by": data.get("updated_by"),
            "updated_at": now,
        }
        ins = (
            supabase.table("legal_obligation_overrides")
            .upsert(payload, on_conflict="company_id,employee_id")
            .execute()
        )
        if not ins.data:
            raise RuntimeError("Erreur lors de l'enregistrement des critères.")
        row = dict(ins.data[0])
        return row

    def get_all_employees_status(self, company_id: str) -> List[Dict[str, Any]]:
        employees = self.get_active_employees(company_id)
        reviews = self.get_completed_reviews_for_company(company_id)
        overrides = self.get_overrides_for_company(company_id)
        by_emp_rev: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in reviews:
            by_emp_rev[str(row["employee_id"])].append(row)
        by_ov = {str(o["employee_id"]): o for o in overrides}
        today = date.today()
        out: List[Dict[str, Any]] = []
        for emp in employees:
            eid = str(emp["id"])
            ov = by_ov.get(eid)
            out.append(_compute_status_for_employee(emp, by_emp_rev.get(eid, []), ov, today))
        return out

    def get_employee_status(self, company_id: str, employee_id: str) -> Optional[Dict[str, Any]]:
        emp = self.get_employee_row(company_id, employee_id)
        if not emp or not _is_active_employee(emp):
            return None
        reviews = self.get_completed_reviews_for_company(company_id)
        emp_reviews = [r for r in reviews if str(r.get("employee_id")) == employee_id]
        r_ov = (
            supabase.table("legal_obligation_overrides")
            .select("*")
            .eq("company_id", company_id)
            .eq("employee_id", employee_id)
            .maybe_single()
            .execute()
        )
        ov = dict(r_ov.data) if r_ov and r_ov.data else None
        return _compute_status_for_employee(emp, emp_reviews, ov, date.today())

    def get_overdue_count(self, company_id: str) -> int:
        rows = self.get_all_employees_status(company_id)
        return sum(1 for r in rows if r.get("professional_interview_status") == "overdue")


legal_obligations_repository: AbstractLegalObligationsRepository = (
    SupabaseLegalObligationsRepository()
)
