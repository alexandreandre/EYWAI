"""Commands — paramètres congés / RTT."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.database import supabase
from app.modules.absences.application.leave_settings_queries import (
    _ensure_employee_in_company,
    get_leave_settings,
)
from app.modules.absences.domain.rules import get_rtt_year_end_status
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.infrastructure.leave_settings_repository import (
    get_employee_adjustment,
    get_leave_policy,
    upsert_employee_adjustment,
    upsert_leave_policy,
)
from app.modules.absences.infrastructure.queries import get_employee_hire_date
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.absences.schemas.leave_settings import (
    EmployeeLeaveAdjustmentUpdate,
    LeaveAdjustmentImportRequest,
    LeaveSettingsUpdate,
    RttYearEndCloseRequest,
)
from app.modules.absences.schemas.leave_settings_responses import (
    EmployeeLeaveAdjustmentResponse,
    LeaveAdjustmentImportResult,
    LeaveSettingsResponse,
    RttYearEndCloseResult,
)

_WRITABLE_POLICY_KEYS = frozenset(
    {
        "cp_acquisition_days_per_month",
        "cp_counting_unit",
        "cp_reference_period_start_month",
        "cp_carryover_enabled",
        "cp_carryover_max_days",
        "rtt_annual_days",
        "rtt_use_calendar_formula",
        "rtt_use_forfait_jours_formula",
        "rtt_forfait_annual_days",
        "rtt_forfait_cp_ouvres_deduction",
        "rtt_forfait_cadres_only",
        "rtt_period_start_month",
        "rtt_period_end_month",
        "rtt_carryover_enabled",
        "rtt_year_end_reminder_enabled",
        "rtt_year_end_reminder_days_before",
    }
)


def update_leave_settings(
    company_id: str, body: LeaveSettingsUpdate
) -> LeaveSettingsResponse:
    current = get_leave_settings(company_id)
    merged = current.model_dump()
    patch = body.model_dump(exclude_unset=True)
    merged.update(patch)

    if merged.get("rtt_use_forfait_jours_formula"):
        merged["rtt_use_calendar_formula"] = False
        merged["rtt_annual_days"] = None
    elif merged.get("rtt_use_calendar_formula"):
        merged["rtt_use_forfait_jours_formula"] = False
        merged["rtt_annual_days"] = None
    elif merged.get("rtt_annual_days") is not None:
        merged["rtt_use_calendar_formula"] = False
        merged["rtt_use_forfait_jours_formula"] = False

    payload = {k: merged[k] for k in _WRITABLE_POLICY_KEYS if k in merged}
    upsert_leave_policy(company_id, payload)
    return get_leave_settings(company_id)


def update_employee_leave_adjustment(
    company_id: str,
    employee_id: str,
    year: int,
    body: EmployeeLeaveAdjustmentUpdate,
) -> EmployeeLeaveAdjustmentResponse:
    _ensure_employee_in_company(employee_id, company_id)
    patch = body.model_dump(exclude_unset=True)
    row = upsert_employee_adjustment(company_id, employee_id, year, patch)
    return EmployeeLeaveAdjustmentResponse(
        employee_id=employee_id,
        year=year,
        cp_n1_opening_balance=float(row.get("cp_n1_opening_balance") or 0),
        cp_n_opening_balance=float(row.get("cp_n_opening_balance") or 0),
        rtt_opening_balance=float(row.get("rtt_opening_balance") or 0),
        rtt_forfeited_at=row.get("rtt_forfeited_at"),
        rtt_forfeited_days=float(row.get("rtt_forfeited_days") or 0),
        note=row.get("note"),
    )


def import_leave_adjustments(
    company_id: str, body: LeaveAdjustmentImportRequest
) -> LeaveAdjustmentImportResult:
    from datetime import date

    from app.modules.absences.domain.rules import (
        compute_cp_period_balances,
        compute_rtt_balance,
    )
    from app.modules.absences.infrastructure.queries import get_employee_hire_date

    errors: list[str] = []
    imported = 0
    employees = _employees_index(company_id)
    policy = get_leave_policy(company_id)
    validated_by_emp: dict[str, list] = {}

    for idx, row in enumerate(body.rows, start=1):
        emp = _match_employee(employees, row)
        if not emp:
            label = row.email or row.matricule or f"{row.first_name} {row.last_name}"
            errors.append(f"Ligne {idx} : employé non trouvé ({label})")
            continue
        eid = str(emp["id"])
        hire_raw = get_employee_hire_date(eid)
        if not hire_raw:
            errors.append(f"Ligne {idx} : date d'embauche manquante")
            continue
        hire_date = (
            date.fromisoformat(hire_raw)
            if isinstance(hire_raw, str)
            else hire_raw
        )
        if eid not in validated_by_emp:
            validated_by_emp[eid] = absence_repository.list_validated_for_employees(
                [eid]
            )
        ref = date(row.year, 12, 31) if row.year != date.today().year else date.today()
        periods = compute_cp_period_balances(
            hire_date,
            validated_by_emp[eid],
            ref,
            policy=policy,
            adjustment=EmployeeLeaveAdjustment.empty(),
        )
        rtt = compute_rtt_balance(
            hire_date,
            validated_by_emp[eid],
            ref,
            policy=policy,
            adjustment=EmployeeLeaveAdjustment.empty(),
        )
        cp_n1_opening = row.cp_n1_solde - max(0.0, float(periods["n1_remaining"]))
        cp_n_opening = row.cp_n_solde - max(0.0, float(periods["n_remaining"]))
        rtt_opening = row.rtt_solde - max(0.0, float(rtt["solde"]))

        upsert_employee_adjustment(
            company_id,
            eid,
            row.year,
            {
                "cp_n1_opening_balance": round(cp_n1_opening, 2),
                "cp_n_opening_balance": round(cp_n_opening, 2),
                "rtt_opening_balance": round(rtt_opening, 2),
            },
        )
        imported += 1

    return LeaveAdjustmentImportResult(imported=imported, errors=errors)


def close_rtt_year_end(
    company_id: str,
    body: RttYearEndCloseRequest,
    user_id: str,
) -> RttYearEndCloseResult:
    policy = get_leave_policy(company_id)
    closed = 0
    total_forfeited = 0.0
    now = datetime.now(timezone.utc).isoformat()

    for employee_id in body.employee_ids:
        _ensure_employee_in_company(employee_id, company_id)
        hire_raw = get_employee_hire_date(employee_id)
        if not hire_raw:
            continue
        from datetime import date

        hire_date = (
            date.fromisoformat(hire_raw)
            if isinstance(hire_raw, str)
            else hire_raw
        )
        validated = absence_repository.list_validated_for_employees([employee_id])
        adj = get_employee_adjustment(employee_id, body.year)
        status = get_rtt_year_end_status(
            hire_date,
            validated,
            body.year,
            policy=policy,
            adjustment=adj,
        )
        remaining = float(status["remaining"])
        if remaining <= 0 or status["already_closed"]:
            continue
        upsert_employee_adjustment(
            company_id,
            employee_id,
            body.year,
            {
                "rtt_forfeited_at": now,
                "rtt_forfeited_days": remaining,
                "rtt_forfeited_by_user_id": user_id,
            },
        )
        closed += 1
        total_forfeited += remaining

    return RttYearEndCloseResult(
        closed_count=closed, total_days_forfeited=round(total_forfeited, 2)
    )


def _employees_index(company_id: str) -> list[dict]:
    resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, email")
        .eq("company_id", company_id)
        .execute()
    )
    return resp.data or []


def _match_employee(employees: list[dict], row) -> dict | None:
    if row.email:
        email_lower = row.email.strip().lower()
        for e in employees:
            if (e.get("email") or "").lower() == email_lower:
                return e
    if row.first_name and row.last_name:
        fn = row.first_name.strip().lower()
        ln = row.last_name.strip().lower()
        for e in employees:
            if (
                (e.get("first_name") or "").lower() == fn
                and (e.get("last_name") or "").lower() == ln
            ):
                return e
    return None
