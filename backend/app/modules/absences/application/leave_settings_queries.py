"""Queries — paramètres congés / RTT."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.application.balance_display import balances_to_api_list
from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.domain.rules import (
    compute_absence_balances,
    get_rtt_year_end_status,
    resolve_rtt_annual_base,
    should_show_rtt_year_end_reminder,
)
from app.modules.companies.domain.public_holidays import normalize_observed_holiday_ids
from app.modules.absences.application.cp_seniority_queries import (
    build_employee_cp_seniority_context,
    compute_and_persist_grant,
    employee_cp_seniority_select,
    employee_cp_seniority_select_without_cadre_dirigeant,
    is_missing_cadre_dirigeant_column_error,
)
from app.modules.absences.application.queries import _cp_balance_extras
from app.modules.absences.infrastructure.cp_seniority_repository import (
    get_cp_seniority_grant,
    get_cp_seniority_settings,
)
from app.modules.absences.infrastructure.fractionnement_repository import (
    get_fractionnement_grant,
)
from app.modules.absences.infrastructure.leave_settings_repository import (
    get_adjustments_by_employees_year,
    get_employee_adjustment,
    get_leave_policy,
    get_leave_policy_row,
)
from app.modules.absences.infrastructure.queries import (
    get_employees_hire_dates_batch,
    get_repos_credits_by_employee_year,
)
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.absences.schemas.leave_settings_responses import (
    EmployeeLeaveAdjustmentResponse,
    EmployeeLeaveBalanceOverviewItem,
    LeaveBalancesOverviewResponse,
    LeaveSettingsResponse,
    RttYearEndOverviewItem,
    RttYearEndOverviewResponse,
)


def _load_observed_holiday_ids(company_id: str) -> list[str] | None:
    resp = (
        supabase.table("companies")
        .select("settings")
        .eq("id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return None
    settings = rows[0].get("settings") or {}
    if not isinstance(settings, dict):
        return None
    public_holidays = settings.get("public_holidays") or {}
    raw_ids = public_holidays.get("observed_holiday_ids")
    if raw_ids is None:
        return None
    if not isinstance(raw_ids, list):
        return None
    return normalize_observed_holiday_ids([str(h) for h in raw_ids])


def _policy_to_response(
    company_id: str, policy: LeavePolicySettings
) -> LeaveSettingsResponse:
    year = date.today().year
    observed = _load_observed_holiday_ids(company_id)
    computed_rtt = resolve_rtt_annual_base(year, policy, observed_holiday_ids=observed)
    return LeaveSettingsResponse(
        company_id=company_id,
        cp_acquisition_days_per_month=policy.cp_acquisition_days_per_month,
        cp_counting_unit=policy.cp_counting_unit,
        cp_reference_period_start_month=policy.cp_reference_period_start_month,
        cp_carryover_enabled=policy.cp_carryover_enabled,
        cp_carryover_max_days=policy.cp_carryover_max_days,
        cp_acquisition_rate_display=policy.cp_acquisition_rate_display,
        cp_annual_days_display=policy.cp_annual_days_display,
        rtt_annual_days=policy.rtt_annual_days,
        rtt_use_calendar_formula=policy.rtt_use_calendar_formula,
        rtt_use_forfait_jours_formula=policy.rtt_use_forfait_jours_formula,
        rtt_forfait_annual_days=policy.rtt_forfait_annual_days,
        rtt_forfait_cp_ouvres_deduction=policy.rtt_forfait_cp_ouvres_deduction,
        rtt_forfait_cadres_only=policy.rtt_forfait_cadres_only,
        rtt_annual_days_computed=computed_rtt,
        rtt_period_start_month=policy.rtt_period_start_month,
        rtt_period_end_month=policy.rtt_period_end_month,
        rtt_carryover_enabled=policy.rtt_carryover_enabled,
        rtt_year_end_reminder_enabled=policy.rtt_year_end_reminder_enabled,
        rtt_year_end_reminder_days_before=policy.rtt_year_end_reminder_days_before,
        configured=get_leave_policy_row(company_id) is not None,
    )


def get_leave_settings(company_id: str) -> LeaveSettingsResponse:
    policy = get_leave_policy(company_id)
    return _policy_to_response(company_id, policy)


def get_employee_leave_adjustment(
    company_id: str, employee_id: str, year: int
) -> EmployeeLeaveAdjustmentResponse:
    _ensure_employee_in_company(employee_id, company_id)
    adj = get_employee_adjustment(employee_id, year)
    return EmployeeLeaveAdjustmentResponse(
        employee_id=employee_id,
        year=year,
        cp_n1_opening_balance=adj.cp_n1_opening_balance,
        cp_n_opening_balance=adj.cp_n_opening_balance,
        rtt_opening_balance=adj.rtt_opening_balance,
        rtt_forfeited_at=adj.rtt_forfeited_at,
        rtt_forfeited_days=adj.rtt_forfeited_days,
        note=adj.note,
    )


def get_leave_balances_overview(
    company_id: str, year: int | None = None
) -> LeaveBalancesOverviewResponse:
    ref_year = year or date.today().year
    today = date.today()
    policy = get_leave_policy(company_id)
    cp_seniority = get_cp_seniority_settings(company_id)

    employees = _list_active_employees(company_id)
    employee_ids = [str(e["id"]) for e in employees]
    hire_dates = get_employees_hire_dates_batch(employee_ids)
    validated = absence_repository.list_validated_for_employees(employee_ids)
    adjustments = get_adjustments_by_employees_year(employee_ids, ref_year)
    repos = get_repos_credits_by_employee_year(employee_ids, ref_year)

    items: list[EmployeeLeaveBalanceOverviewItem] = []
    for emp in employees:
        eid = str(emp["id"])
        hire_raw = hire_dates.get(eid)
        if not hire_raw:
            continue
        hire_date = (
            date.fromisoformat(hire_raw) if isinstance(hire_raw, str) else hire_raw
        )
        emp_validated = [r for r in validated if r["employee_id"] == eid]
        adj = adjustments.get(eid)
        ctx = build_employee_cp_seniority_context(emp)
        if cp_seniority.is_active:
            compute_and_persist_grant(
                company_id, eid, cp_seniority, ctx, today, policy=policy
            )
        soldes = compute_absence_balances(
            hire_date,
            emp_validated,
            today,
            repos_acquis=repos.get(eid, 0.0),
            policy=policy,
            adjustment=adj,
            cp_seniority=cp_seniority,
            employee_ctx=ctx,
        )
        cp = soldes["conges_payes"]
        n1 = soldes.get("conges_payes_n1") or {}
        n = soldes.get("conges_payes_n") or {}
        cp_grant = get_cp_seniority_grant(eid, ref_year)
        frac_grant = get_fractionnement_grant(eid, ref_year)
        items.append(
            EmployeeLeaveBalanceOverviewItem(
                employee_id=eid,
                first_name=emp.get("first_name") or "",
                last_name=emp.get("last_name") or "",
                email=emp.get("email"),
                cp_n1_remaining=max(0.0, float(n1.get("solde", 0))),
                cp_n_remaining=max(0.0, float(n.get("solde", 0))),
                cp_total_remaining=max(0.0, float(cp.get("solde", 0))),
                cp_legal_days=float(soldes.get("cp_legal_days") or 0),
                cp_seniority_days=float(soldes.get("cp_seniority_days") or 0),
                fractionnement_days=float((frac_grant or {}).get("days_granted") or 0),
                cp_seniority_status=(cp_grant or {}).get("status"),
                rtt_remaining=max(0.0, float(soldes["rtt"].get("solde", 0))),
                rtt_opening_balance=float(adj.rtt_opening_balance or 0) if adj else 0.0,
                adjustment_note=adj.note if adj else None,
            )
        )

    return LeaveBalancesOverviewResponse(year=ref_year, employees=items)


def get_rtt_year_end_overview(
    company_id: str, year: int | None = None
) -> RttYearEndOverviewResponse:
    ref_year = year or date.today().year
    today = date.today()
    policy = get_leave_policy(company_id)
    reminder = should_show_rtt_year_end_reminder(today, policy)

    employees = _list_active_employees(company_id)
    employee_ids = [str(e["id"]) for e in employees]
    hire_dates = get_employees_hire_dates_batch(employee_ids)
    validated = absence_repository.list_validated_for_employees(employee_ids)
    adjustments = get_adjustments_by_employees_year(employee_ids, ref_year)

    items: list[RttYearEndOverviewItem] = []
    for emp in employees:
        eid = str(emp["id"])
        hire_raw = hire_dates.get(eid)
        if not hire_raw:
            continue
        hire_date = (
            date.fromisoformat(hire_raw) if isinstance(hire_raw, str) else hire_raw
        )
        emp_validated = [r for r in validated if r["employee_id"] == eid]
        adj = adjustments.get(eid)
        employee_ctx = build_employee_cp_seniority_context(emp)
        status = get_rtt_year_end_status(
            hire_date,
            emp_validated,
            ref_year,
            policy=policy,
            adjustment=adj,
            employee_ctx=employee_ctx,
        )
        if float(status["remaining"]) <= 0 and not status["already_closed"]:
            continue
        items.append(
            RttYearEndOverviewItem(
                employee_id=eid,
                first_name=emp.get("first_name") or "",
                last_name=emp.get("last_name") or "",
                rtt_remaining=float(status["remaining"]),
                already_closed=bool(status["already_closed"]),
                closure_required=bool(status["closure_required"]),
            )
        )

    return RttYearEndOverviewResponse(
        year=ref_year, reminder_active=reminder, employees=items
    )


def compute_balances_for_employee(
    company_id: str,
    employee_id: str,
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
    repos_acquis: float = 0.0,
) -> list[dict]:
    policy = get_leave_policy(company_id)
    cp_seniority = get_cp_seniority_settings(company_id)
    adjustment = get_employee_adjustment(employee_id, ref_date.year)
    observed = _load_observed_holiday_ids(company_id)
    rtt_base = resolve_rtt_annual_base(
        ref_date.year, policy, observed_holiday_ids=observed
    )
    extras = _cp_balance_extras(employee_id, ref_date, company_id, policy, cp_seniority)
    soldes = compute_absence_balances(
        hire_date,
        validated_requests,
        ref_date,
        repos_acquis=repos_acquis,
        rtt_annual_base=rtt_base,
        policy=policy,
        adjustment=adjustment,
        **extras,
    )
    return balances_to_api_list(soldes, policy=policy, cp_seniority=cp_seniority)


def _list_active_employees(company_id: str) -> list[dict[str, Any]]:
    select_fields = (
        f"{employee_cp_seniority_select(include_id=True, include_status=True)}, email"
    )
    try:
        resp = (
            supabase.table("employees")
            .select(select_fields)
            .eq("company_id", company_id)
            .in_("employment_status", ["actif", "active", "en_onboarding"])
            .execute()
        )
    except Exception as exc:
        if not is_missing_cadre_dirigeant_column_error(exc):
            raise
        resp = (
            supabase.table("employees")
            .select(
                f"{employee_cp_seniority_select_without_cadre_dirigeant(include_id=True, include_status=True)}, email"
            )
            .eq("company_id", company_id)
            .in_("employment_status", ["actif", "active", "en_onboarding"])
            .execute()
        )
    return resp.data or []


def _ensure_employee_in_company(employee_id: str, company_id: str) -> None:
    resp = (
        supabase.table("employees")
        .select("id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not resp.data:
        raise LookupError("Employé introuvable dans cette entreprise.")
