"""Commands — paramètres congés / RTT."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

from app.core.database import supabase
from app.modules.absences.application.leave_settings_queries import (
    _ensure_employee_in_company,
    get_leave_settings,
)
from app.modules.absences.application.cp_seniority_queries import (
    build_employee_cp_seniority_context,
    employee_cp_seniority_select,
    employee_cp_seniority_select_without_cadre_dirigeant,
    is_missing_cadre_dirigeant_column_error,
)
from app.modules.absences.domain.rules import (
    _rtt_eligible_for_employee,
    compute_rtt_balance,
    get_rtt_year_end_status,
)
from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
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


def bulletin_reference_date(year: int, month: int | None = None) -> date:
    """Date de référence pour un solde CP issu d'un bulletin (fin de période paie)."""
    today = date.today()
    if month is not None and 1 <= month <= 12:
        _, last_day = calendar.monthrange(year, month)
        return min(date(year, month, last_day), today)
    if year < today.year:
        return date(year, 12, 31)
    return today


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


def apply_rtt_solde_manual(
    company_id: str,
    employee_id: str,
    year: int,
    *,
    rtt_solde: float,
    note: str | None = None,
) -> EmployeeLeaveAdjustmentResponse:
    """Convertit un solde RTT absolu en ajustement d'ouverture (CP inchangés)."""
    from datetime import date

    _ensure_employee_in_company(employee_id, company_id)
    hire_raw = get_employee_hire_date(employee_id)
    if not hire_raw:
        raise ValueError("Date d'embauche manquante.")
    hire_date = date.fromisoformat(hire_raw) if isinstance(hire_raw, str) else hire_raw

    emp_resp = (
        supabase.table("employees")
        .select(
            "id, first_name, last_name, email, hire_date, employment_status, "
            "statut, prior_service_months, specificites_paie, date_naissance"
        )
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    emp_rows = emp_resp.data or []
    if not emp_rows:
        raise LookupError("Employé introuvable dans cette entreprise.")
    employee_ctx = build_employee_cp_seniority_context(emp_rows[0])

    policy = get_leave_policy(company_id)
    if not _rtt_eligible_for_employee(policy, employee_ctx):
        raise ValueError("Salarié non éligible aux RTT.")

    validated = absence_repository.list_validated_for_employees([employee_id])
    ref = date(year, 12, 31) if year != date.today().year else date.today()
    rtt = compute_rtt_balance(
        hire_date,
        validated,
        ref,
        policy=policy,
        adjustment=EmployeeLeaveAdjustment.empty(),
        employee_ctx=employee_ctx,
    )
    rtt_opening = rtt_solde - max(0.0, float(rtt["solde"]))

    payload: dict = {"rtt_opening_balance": round(rtt_opening, 2)}
    if note:
        payload["note"] = note
    row = upsert_employee_adjustment(company_id, employee_id, year, payload)
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


def apply_cp_solde_import(
    company_id: str,
    employee_id: str,
    year: int,
    *,
    cp_n1_solde: float,
    cp_n_solde: float,
    rtt_solde: float = 0.0,
    month: int | None = None,
    note: str | None = None,
) -> None:
    """Convertit des soldes CP/RTT affichés en soldes d'ouverture et upsert."""
    from app.modules.absences.domain.rules import (
        compute_cp_period_balances,
        compute_rtt_balance,
    )
    from app.modules.absences.infrastructure.queries import get_employee_hire_date

    hire_raw = get_employee_hire_date(employee_id)
    if not hire_raw:
        raise ValueError("Date d'embauche manquante.")
    hire_date = date.fromisoformat(hire_raw) if isinstance(hire_raw, str) else hire_raw
    policy = get_leave_policy(company_id)
    validated = absence_repository.list_validated_for_employees([employee_id])
    ref = bulletin_reference_date(year, month)
    periods = compute_cp_period_balances(
        hire_date,
        validated,
        ref,
        policy=policy,
        adjustment=EmployeeLeaveAdjustment.empty(),
    )
    rtt = compute_rtt_balance(
        hire_date,
        validated,
        ref,
        policy=policy,
        adjustment=EmployeeLeaveAdjustment.empty(),
    )
    cp_n1_opening = cp_n1_solde - max(0.0, float(periods["n1_remaining"]))
    cp_n_opening = cp_n_solde - max(0.0, float(periods["n_remaining"]))
    rtt_opening = rtt_solde - max(0.0, float(rtt["solde"]))

    payload: dict = {
        "cp_n1_opening_balance": round(cp_n1_opening, 2),
        "cp_n_opening_balance": round(cp_n_opening, 2),
        "rtt_opening_balance": round(rtt_opening, 2),
    }
    if note:
        payload["note"] = note
    upsert_employee_adjustment(company_id, employee_id, year, payload)


def import_leave_adjustments(
    company_id: str, body: LeaveAdjustmentImportRequest
) -> LeaveAdjustmentImportResult:
    from app.modules.absences.infrastructure.queries import get_employee_hire_date

    errors: list[str] = []
    imported = 0
    employees = _employees_index(company_id)

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
        try:
            apply_cp_solde_import(
                company_id,
                eid,
                row.year,
                cp_n1_solde=row.cp_n1_solde,
                cp_n_solde=row.cp_n_solde,
                rtt_solde=row.rtt_solde,
            )
        except ValueError as exc:
            errors.append(f"Ligne {idx} : {exc}")
            continue
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
            date.fromisoformat(hire_raw) if isinstance(hire_raw, str) else hire_raw
        )
        validated = absence_repository.list_validated_for_employees([employee_id])
        adj = get_employee_adjustment(employee_id, body.year)
        try:
            emp_resp = (
                supabase.table("employees")
                .select(
                    employee_cp_seniority_select(include_id=True, include_status=True)
                )
                .eq("id", employee_id)
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
        except Exception as exc:
            if not is_missing_cadre_dirigeant_column_error(exc):
                raise
            emp_resp = (
                supabase.table("employees")
                .select(
                    employee_cp_seniority_select_without_cadre_dirigeant(
                        include_id=True,
                        include_status=True,
                    )
                )
                .eq("id", employee_id)
                .eq("company_id", company_id)
                .limit(1)
                .execute()
            )
        emp_rows = emp_resp.data or []
        employee_ctx = (
            build_employee_cp_seniority_context(emp_rows[0]) if emp_rows else None
        )
        status = get_rtt_year_end_status(
            hire_date,
            validated,
            body.year,
            policy=policy,
            adjustment=adj,
            employee_ctx=employee_ctx,
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
            if (e.get("first_name") or "").lower() == fn and (
                e.get("last_name") or ""
            ).lower() == ln:
                return e
    return None
