"""
Règles métier pures — migrées depuis api/routers/absences.py.

Aucun accès DB : toutes les données passent en paramètres.
"""

from __future__ import annotations

import calendar
import math
from datetime import date, timedelta

from app.modules.absences.domain.enums import SALARY_CERTIFICATE_ABSENCE_TYPES
from app.modules.absences.domain.cp_seniority import (
    CpSenioritySettings,
    EmployeeCpSeniorityContext,
    compute_cp_seniority_grant,
)
from app.modules.absences.domain.leave_policy import (
    DEFAULT_LEAVE_POLICY,
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
    RTT_ANNUAL_DAYS_DEFAULT,
)


def get_cp_reference_period(
    ref_date: date, *, start_month: int = 6
) -> tuple[date, date]:
    """
    Période de référence CP en cours à la date donnée (1er juin N → 31 mai N+1 par défaut).
    """
    if ref_date.month >= start_month:
        period_start = date(ref_date.year, start_month, 1)
        end_year = ref_date.year + 1
    else:
        period_start = date(ref_date.year - 1, start_month, 1)
        end_year = ref_date.year
    end_month = start_month - 1
    if end_month < 1:
        end_month = 12
        end_year -= 1
    _, last_day = calendar.monthrange(end_year, end_month)
    return period_start, date(end_year, end_month, last_day)


def get_cp_previous_reference_period(
    ref_date: date, *, start_month: int = 6
) -> tuple[date, date]:
    """Période de référence CP immédiatement précédente."""
    current_start, _ = get_cp_reference_period(ref_date, start_month=start_month)
    prev_start = date(current_start.year - 1, start_month, 1)
    end_month = start_month - 1
    end_year = current_start.year
    if end_month < 1:
        end_month = 12
        end_year = current_start.year - 1
    _, last_day = calendar.monthrange(end_year, end_month)
    return prev_start, date(end_year, end_month, last_day)


def _months_worked_in_period(
    hire_date: date, period_start: date, acquisition_end: date
) -> int:
    if hire_date > acquisition_end:
        return 0
    start_of_calculation = max(hire_date, period_start)
    return (
        (acquisition_end.year - start_of_calculation.year) * 12
        + (acquisition_end.month - start_of_calculation.month)
        + 1
    )


def _acquired_cp_from_months(
    months_worked: int, days_per_month: float = 2.5
) -> float:
    if months_worked <= 0:
        return 0.0
    return float(math.ceil(months_worked * days_per_month))


def calculate_acquired_cp(
    hire_date: date,
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
) -> float:
    policy = policy or DEFAULT_LEAVE_POLICY
    period_start, period_end = get_cp_reference_period(
        ref_date, start_month=policy.cp_reference_period_start_month
    )
    acquisition_end = min(ref_date, period_end)
    months_worked = _months_worked_in_period(hire_date, period_start, acquisition_end)
    return _acquired_cp_from_months(
        months_worked, policy.cp_acquisition_rate_internal
    )


def calculate_acquired_cp_for_period(
    hire_date: date,
    period_start: date,
    period_end: date,
    *,
    policy: LeavePolicySettings | None = None,
) -> float:
    policy = policy or DEFAULT_LEAVE_POLICY
    months_worked = _months_worked_in_period(hire_date, period_start, period_end)
    return _acquired_cp_from_months(
        months_worked, policy.cp_acquisition_rate_internal
    )


def count_weekdays_in_year(year: int) -> int:
    total = 0
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    while d <= end:
        if d.weekday() < 5:
            total += 1
        d += timedelta(days=1)
    return total


def calculate_rtt_annual_calendar(year: int) -> float:
    """
    RTT forfait-jours : ~10 j/an, +1 jour les années bissextiles (jours dans l'année).
    """
    if calendar.isleap(year):
        return 11.0
    return 10.0


def resolve_rtt_annual_base(
    year: int,
    policy: LeavePolicySettings | None = None,
    *,
    observed_holiday_ids: list[str] | None = None,
    forfait_days_override: int | float | None = None,
) -> float:
    policy = policy or DEFAULT_LEAVE_POLICY
    if policy.rtt_annual_days is not None:
        return float(policy.rtt_annual_days)
    if policy.rtt_use_forfait_jours_formula:
        from app.modules.absences.domain.rtt_forfait import (
            calculate_rtt_annual_forfait_jours,
        )

        forfait_days = (
            int(forfait_days_override)
            if forfait_days_override is not None
            else policy.rtt_forfait_annual_days
        )
        return calculate_rtt_annual_forfait_jours(
            year,
            forfait_days=forfait_days,
            cp_ouvres_deduction=policy.rtt_forfait_cp_ouvres_deduction,
            observed_holiday_ids=observed_holiday_ids,
        )
    if policy.rtt_use_calendar_formula:
        return calculate_rtt_annual_calendar(year)
    return RTT_ANNUAL_DAYS_DEFAULT


def _rtt_eligible_for_employee(
    policy: LeavePolicySettings,
    employee_ctx: EmployeeCpSeniorityContext | None,
) -> bool:
    if not policy.rtt_use_forfait_jours_formula:
        return True
    if not policy.rtt_forfait_cadres_only:
        return True
    return bool(employee_ctx and employee_ctx.is_forfait)


def _rtt_period_bounds(year: int, policy: LeavePolicySettings) -> tuple[date, date]:
    start = date(year, policy.rtt_period_start_month, 1)
    _, last_day = calendar.monthrange(year, policy.rtt_period_end_month)
    end = date(year, policy.rtt_period_end_month, last_day)
    return start, end


def calculate_acquired_rtt(
    hire_date: date,
    today: date,
    rtt_annual_base: float | None = None,
    *,
    policy: LeavePolicySettings | None = None,
) -> float:
    """RTT acquis pour l'année civile (prorata si embauche en cours d'année)."""
    policy = policy or DEFAULT_LEAVE_POLICY
    base = (
        rtt_annual_base
        if rtt_annual_base is not None
        else resolve_rtt_annual_base(today.year, policy)
    )
    period_start, period_end = _rtt_period_bounds(today.year, policy)
    if hire_date > period_end:
        return 0.0
    if hire_date <= period_start:
        return base
    months_worked = (
        (today.year - hire_date.year) * 12 + (today.month - hire_date.month) + 1
    )
    acquired_rtt = (base / 12) * months_worked
    return round(min(acquired_rtt, base), 2)


def requires_salary_certificate(absence_type: str) -> bool:
    return absence_type in SALARY_CERTIFICATE_ABSENCE_TYPES


def _parse_absence_day(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def count_absence_days_taken(
    requests: list[dict],
    absence_type: str,
    ref_date: date,
    *,
    period_start: date | None = None,
    period_end: date | None = None,
) -> float:
    effective_end = ref_date
    if period_end is not None:
        effective_end = min(ref_date, period_end)

    total = 0.0
    for req in requests:
        if req.get("type") != absence_type:
            continue
        days_in_range = []
        for day in req.get("selected_days") or []:
            parsed = _parse_absence_day(day)
            if parsed is None:
                continue
            if parsed > effective_end:
                continue
            if period_start is not None and parsed < period_start:
                continue
            days_in_range.append(parsed)

        if absence_type == "conge_paye" and req.get("jours_payes") is not None:
            total += min(len(days_in_range), float(req["jours_payes"]))
        else:
            total += len(days_in_range)
    return total


def _balance(acquis: float, pris: float) -> dict[str, float]:
    return {
        "acquis": acquis,
        "pris": pris,
        "solde": round(acquis - pris, 2),
    }


def _apply_cp_carryover_cap(n1_solde: float, policy: LeavePolicySettings) -> float:
    if policy.cp_carryover_max_days is None:
        return n1_solde
    return min(n1_solde, float(policy.cp_carryover_max_days))


def _supplemental_cp_for_period_end(
    period_end: date,
    *,
    cp_seniority: CpSenioritySettings | None,
    employee_ctx: EmployeeCpSeniorityContext | None,
    policy: LeavePolicySettings,
) -> float:
    if not cp_seniority or not cp_seniority.is_active or not employee_ctx:
        return 0.0
    grant = compute_cp_seniority_grant(
        cp_seniority, employee_ctx, period_end, policy=policy
    )
    return grant.days_granted


def compute_cp_period_balances(
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    cp_seniority: CpSenioritySettings | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
) -> dict[str, dict[str, float]]:
    """Soldes CP période N-1 et N avec report optionnel."""
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()
    start_month = policy.cp_reference_period_start_month

    current_start, current_end = get_cp_reference_period(
        ref_date, start_month=start_month
    )
    prev_start, prev_end = get_cp_previous_reference_period(
        ref_date, start_month=start_month
    )

    prev_acquis = calculate_acquired_cp_for_period(
        hire_date, prev_start, prev_end, policy=policy
    )
    prev_supp = _supplemental_cp_for_period_end(
        prev_end,
        cp_seniority=cp_seniority,
        employee_ctx=employee_ctx,
        policy=policy,
    )
    prev_acquis += prev_supp
    prev_pris = count_absence_days_taken(
        validated_requests,
        "conge_paye",
        ref_date,
        period_start=prev_start,
        period_end=prev_end,
    )
    n1_raw = prev_acquis - prev_pris + adjustment.cp_n1_opening_balance
    n1_available = _apply_cp_carryover_cap(max(0.0, n1_raw), policy)

    current_acquis = calculate_acquired_cp(hire_date, ref_date, policy=policy)
    current_supp = _supplemental_cp_for_period_end(
        current_end,
        cp_seniority=cp_seniority,
        employee_ctx=employee_ctx,
        policy=policy,
    )
    current_acquis += current_supp
    days_taken_current = count_absence_days_taken(
        validated_requests,
        "conge_paye",
        ref_date,
        period_start=current_start,
        period_end=current_end,
    )

    if policy.cp_carryover_enabled:
        taken_from_n1 = min(days_taken_current, n1_available)
        taken_from_n = days_taken_current - taken_from_n1
        n1_remaining = round(n1_available - taken_from_n1, 2)
        n_remaining = round(
            current_acquis + adjustment.cp_n_opening_balance - taken_from_n, 2
        )
    else:
        n1_remaining = round(n1_available, 2) if n1_available > 0 else 0.0
        taken_from_n = days_taken_current
        n_remaining = round(
            current_acquis + adjustment.cp_n_opening_balance - taken_from_n, 2
        )

    return {
        "periode_precedente": _balance(n1_available, n1_available - n1_remaining),
        "periode_courante": _balance(
            current_acquis + adjustment.cp_n_opening_balance, taken_from_n
        ),
        "n1_remaining": n1_remaining,
        "n_remaining": max(0.0, n_remaining),
        "total_remaining": max(0.0, round(n1_remaining + max(0.0, n_remaining), 2)),
        "cp_seniority_n1": prev_supp,
        "cp_seniority_n": current_supp,
    }


def compute_cp_balances_for_bulletin(
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    cp_seniority: CpSenioritySettings | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
) -> dict[str, dict[str, float | str]]:
    policy = policy or DEFAULT_LEAVE_POLICY
    start_month = policy.cp_reference_period_start_month
    current_start, current_end = get_cp_reference_period(
        ref_date, start_month=start_month
    )
    prev_start, prev_end = get_cp_previous_reference_period(
        ref_date, start_month=start_month
    )

    periods = compute_cp_period_balances(
        hire_date,
        validated_requests,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=employee_ctx,
    )

    current = dict(periods["periode_courante"])
    current["periode"] = (
        f"{current_start.strftime('%d/%m/%Y')} – {current_end.strftime('%d/%m/%Y')}"
    )
    previous = dict(periods["periode_precedente"])
    previous["periode"] = (
        f"{prev_start.strftime('%d/%m/%Y')} – {prev_end.strftime('%d/%m/%Y')}"
    )

    return {
        "periode_courante": current,
        "periode_precedente": previous,
    }


def compute_rtt_balance(
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    rtt_annual_base: float | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
    observed_holiday_ids: list[str] | None = None,
    forfait_days_override: int | float | None = None,
) -> dict[str, float]:
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()

    if not _rtt_eligible_for_employee(policy, employee_ctx):
        return _balance(0.0, 0.0)

    rtt_base = (
        rtt_annual_base
        if rtt_annual_base is not None
        else resolve_rtt_annual_base(
            ref_date.year,
            policy,
            observed_holiday_ids=observed_holiday_ids,
            forfait_days_override=forfait_days_override,
        )
    )
    period_start, period_end = _rtt_period_bounds(ref_date.year, policy)

    rtt_acquis = (
        calculate_acquired_rtt(hire_date, ref_date, rtt_base, policy=policy)
        + adjustment.rtt_opening_balance
    )
    rtt_pris = count_absence_days_taken(
        validated_requests,
        "rtt",
        ref_date,
        period_start=period_start,
        period_end=period_end,
    )
    forfeited = float(adjustment.rtt_forfeited_days or 0)
    effective_pris = rtt_pris + forfeited
    return _balance(rtt_acquis, effective_pris)


def compute_absence_balances(
    hire_date: date,
    validated_requests: list[dict],
    ref_date: date,
    *,
    repos_acquis: float = 0.0,
    rtt_annual_base: float | None = None,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    cp_seniority: CpSenioritySettings | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
) -> dict[str, dict[str, float]]:
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()

    cp_periods = compute_cp_period_balances(
        hire_date,
        validated_requests,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=employee_ctx,
    )
    seniority_n = float(cp_periods.get("cp_seniority_n") or 0)

    if policy.cp_carryover_enabled:
        cp = {
            "acquis": round(
                cp_periods["periode_precedente"]["acquis"]
                + cp_periods["periode_courante"]["acquis"],
                2,
            ),
            "pris": round(
                cp_periods["periode_precedente"]["pris"]
                + cp_periods["periode_courante"]["pris"],
                2,
            ),
            "solde": cp_periods["total_remaining"],
            "n1_remaining": cp_periods["n1_remaining"],
            "n_remaining": cp_periods["n_remaining"],
        }
    else:
        current = cp_periods["periode_courante"]
        cp = {
            "acquis": current["acquis"],
            "pris": current["pris"],
            "solde": max(0.0, current["solde"]),
        }

    rtt = compute_rtt_balance(
        hire_date,
        validated_requests,
        ref_date,
        policy=policy,
        adjustment=adjustment,
        rtt_annual_base=rtt_annual_base,
        employee_ctx=employee_ctx,
    )

    repos_pris = count_absence_days_taken(
        validated_requests,
        "repos_compensateur",
        ref_date,
        period_start=date(ref_date.year, 1, 1),
        period_end=date(ref_date.year, 12, 31),
    )

    cp_seniority_balance = _balance(seniority_n, 0.0)

    return {
        "conges_payes": cp,
        "conges_payes_n1": cp_periods["periode_precedente"],
        "conges_payes_n": cp_periods["periode_courante"],
        "conges_payes_anciennete": cp_seniority_balance,
        "cp_seniority_days": seniority_n,
        "cp_legal_days": round(max(0.0, cp.get("acquis", 0) - seniority_n), 2),
        "rtt": rtt,
        "repos_compensateur": _balance(repos_acquis, repos_pris),
    }


def _count_cp_days_in_requests(
    requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings,
    statuses: tuple[str, ...],
) -> float:
    current_start, current_end = get_cp_reference_period(
        ref_date, start_month=policy.cp_reference_period_start_month
    )
    filtered = [r for r in requests if r.get("status") in statuses]
    return count_absence_days_taken(
        filtered,
        "conge_paye",
        current_end,
        period_start=current_start,
        period_end=current_end,
    )


def count_conge_paye_days_committed(
    requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
    hire_date: date | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
) -> float:
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()
    validated = [
        r
        for r in requests
        if r.get("type") == "conge_paye" and r.get("status") == "validated"
    ]
    pending = [
        r
        for r in requests
        if r.get("type") == "conge_paye" and r.get("status") == "pending"
    ]
    taken = _count_cp_days_in_requests(
        validated, ref_date, policy=policy, statuses=("validated",)
    )
    reserved = _count_cp_days_in_requests(
        pending, ref_date, policy=policy, statuses=("pending",)
    )
    return taken + reserved


def get_available_conge_paye_days(
    hire_date: date,
    requests: list[dict],
    ref_date: date,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    extra_committed_days: float = 0.0,
    cp_seniority: CpSenioritySettings | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
) -> float:
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()
    extra = max(0.0, float(extra_committed_days))

    if policy.cp_carryover_enabled:
        validated = [r for r in requests if r.get("status") == "validated"]
        cp_periods = compute_cp_period_balances(
            hire_date,
            validated,
            ref_date,
            policy=policy,
            adjustment=adjustment,
            cp_seniority=cp_seniority,
            employee_ctx=employee_ctx,
        )
        pending_days = _count_cp_days_in_requests(
            requests, ref_date, policy=policy, statuses=("pending",)
        )
        return max(0.0, round(cp_periods["total_remaining"] - pending_days - extra, 2))

    committed = count_conge_paye_days_committed(requests, ref_date, policy=policy)
    cp_periods = compute_cp_period_balances(
        hire_date,
        [r for r in requests if r.get("status") == "validated"],
        ref_date,
        policy=policy,
        adjustment=adjustment,
        cp_seniority=cp_seniority,
        employee_ctx=employee_ctx,
    )
    acquis = cp_periods["periode_courante"]["acquis"]
    return max(0.0, round(acquis - committed - extra, 2))


def validate_conge_paye_request_days(
    hire_date: date,
    requests: list[dict],
    selected_days: list[date],
    ref_date: date | None = None,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    extra_committed_days: float = 0.0,
    cp_seniority: CpSenioritySettings | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
) -> None:
    ref = ref_date or date.today()
    available = get_available_conge_paye_days(
        hire_date,
        requests,
        ref,
        policy=policy,
        adjustment=adjustment,
        extra_committed_days=extra_committed_days,
        cp_seniority=cp_seniority,
        employee_ctx=employee_ctx,
    )
    requested = len(selected_days)
    if requested <= available:
        return
    if available <= 0:
        raise ValueError(
            "Solde de congés payés insuffisant. Rapprochez-vous de votre direction "
            "pour toute demande hors droits acquis."
        )
    avail_label = (
        str(int(available)) if available == int(available) else f"{available:.1f}"
    )
    raise ValueError(
        f"Solde de congés payés insuffisant : il vous reste {avail_label} jour(s) "
        f"disponible(s) pour {requested} jour(s) demandé(s). "
        "Rapprochez-vous de votre direction pour une demande hors solde."
    )


def get_rtt_year_end_status(
    hire_date: date,
    validated_requests: list[dict],
    year: int,
    *,
    policy: LeavePolicySettings | None = None,
    adjustment: EmployeeLeaveAdjustment | None = None,
    employee_ctx: EmployeeCpSeniorityContext | None = None,
) -> dict[str, float | bool]:
    """État RTT en fin d'année pour clôture RH."""
    policy = policy or DEFAULT_LEAVE_POLICY
    adjustment = adjustment or EmployeeLeaveAdjustment.empty()
    ref = date(year, 12, 31)
    rtt = compute_rtt_balance(
        hire_date,
        validated_requests,
        ref,
        policy=policy,
        adjustment=adjustment,
        employee_ctx=employee_ctx,
    )
    remaining = max(0.0, float(rtt["solde"]))
    already_closed = adjustment.rtt_forfeited_at is not None
    return {
        "remaining": remaining,
        "forfeited": float(adjustment.rtt_forfeited_days or 0),
        "closure_required": remaining > 0 and not already_closed,
        "already_closed": already_closed,
    }


def should_show_rtt_year_end_reminder(
    ref_date: date, policy: LeavePolicySettings | None = None
) -> bool:
    policy = policy or DEFAULT_LEAVE_POLICY
    if not policy.rtt_year_end_reminder_enabled:
        return False
    days_before = policy.rtt_year_end_reminder_days_before
    reminder_start = date(ref_date.year, 12, 31) - timedelta(days=days_before)
    return ref_date >= reminder_start and ref_date.month == 12
