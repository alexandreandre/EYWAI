# app/modules/cse/application/delegation_service.py
"""
Orchestration heures de délégation conformes — domain + infrastructure.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from app.modules.cse.domain.exceptions import (
    DelegationNotFoundError,
    DelegationValidationError,
)
from app.modules.cse.domain.delegation import (
    DelegationHourRecord,
    DelegationTransferRecord,
    MonthlyBalanceInput,
    aggregate_hours_by_month,
    aggregate_transfers_by_month,
    annual_register_row,
    compute_monthly_balance,
    compute_rolling_balances,
    credit_base,
    validate_transfer,
)
from app.modules.cse.infrastructure.delegation_queries import (
    count_active_employees,
    fetch_active_mandate_with_override,
    fetch_delegation_config,
    fetch_delegation_hours_raw,
    fetch_delegation_requests,
    fetch_delegation_transfers,
    insert_delegation_request,
    insert_delegation_transfer,
    insert_payroll_entry,
    update_delegation_request,
    upsert_delegation_config_row,
)
from app.modules.cse.schemas import (
    DelegationConfigRead,
    DelegationConfigUpdate,
    DelegationCreditRead,
    DelegationHourCreate,
    DelegationQuotaRead,
    DelegationRegisterRow,
    DelegationRequestCreate,
    DelegationRequestRead,
    DelegationRequestUpdate,
    DelegationSummary,
    DelegationTransferCreate,
    DelegationTransferRead,
)


def _month_bounds(year: int, month: int) -> Tuple[date, date]:
    last_day = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last_day)


def _months_range(start: date, end: date) -> List[Tuple[int, int]]:
    months: List[Tuple[int, int]] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return months


def _resolve_reference_headcount(company_id: str) -> Tuple[int, Optional[date], bool, bool]:
    config = fetch_delegation_config(company_id)
    if config:
        ref_date = config.get("reference_date")
        if isinstance(ref_date, str):
            ref_date = datetime.fromisoformat(ref_date).date()
        return (
            int(config["reference_headcount"]),
            ref_date,
            bool(config.get("report_enabled", True)),
            bool(config.get("mutualisation_enabled", True)),
        )
    return count_active_employees(company_id), None, True, True


def _mandate_context(company_id: str, employee_id: str) -> Dict[str, Any]:
    mandate = fetch_active_mandate_with_override(company_id, employee_id)
    if not mandate:
        return {"role": "autre", "monthly_hours_override": None}
    override = mandate.get("monthly_hours_override")
    return {
        "role": mandate.get("role") or "autre",
        "monthly_hours_override": float(override) if override is not None else None,
    }


def _load_monthly_data(
    company_id: str,
    employee_id: str,
    months: List[Tuple[int, int]],
) -> Tuple[Dict[Tuple[int, int], float], Dict[Tuple[int, int], float], Dict[Tuple[int, int], float]]:
    if not months:
        return {}, {}, {}
    first_y, first_m = months[0]
    last_y, last_m = months[-1]
    start, _ = _month_bounds(first_y, first_m)
    _, end = _month_bounds(last_y, last_m)

    raw_hours = fetch_delegation_hours_raw(company_id, employee_id, start, end)
    hour_records = [
        DelegationHourRecord(
            usage_date=datetime.fromisoformat(h["date"]).date()
            if isinstance(h["date"], str)
            else h["date"],
            duration_hours=float(h["duration_hours"]),
            source=h.get("source") or "propre",
            origin_month=None,
        )
        for h in raw_hours
    ]
    transfers_raw = fetch_delegation_transfers(company_id, employee_id)
    transfers = [
        DelegationTransferRecord(
            period_year=int(t["period_year"]),
            period_month=int(t["period_month"]),
            from_employee_id=str(t["from_employee_id"]),
            to_employee_id=str(t["to_employee_id"]),
            hours=float(t["hours"]),
            employer_notified_at=datetime.fromisoformat(t["employer_notified_at"]).date()
            if t.get("employer_notified_at")
            else None,
        )
        for t in transfers_raw
    ]
    return (
        aggregate_hours_by_month(hour_records),
        aggregate_transfers_by_month(transfers, "in", employee_id),
        aggregate_transfers_by_month(transfers, "out", employee_id),
    )


def get_delegation_config(company_id: str) -> DelegationConfigRead:
    config = fetch_delegation_config(company_id)
    headcount_fallback = count_active_employees(company_id)
    if not config:
        return DelegationConfigRead(
            id="",
            company_id=company_id,
            reference_headcount=headcount_fallback,
            reference_date=date.today(),
            report_enabled=True,
            mutualisation_enabled=True,
            is_configured=False,
            current_headcount=headcount_fallback,
        )
    ref_date = config.get("reference_date")
    if isinstance(ref_date, str):
        ref_date = datetime.fromisoformat(ref_date).date()
    return DelegationConfigRead(
        id=config["id"],
        company_id=company_id,
        reference_headcount=int(config["reference_headcount"]),
        reference_date=ref_date,
        report_enabled=bool(config.get("report_enabled", True)),
        mutualisation_enabled=bool(config.get("mutualisation_enabled", True)),
        is_configured=True,
        current_headcount=headcount_fallback,
    )


def upsert_delegation_config(
    company_id: str, data: DelegationConfigUpdate, updated_by: str
) -> DelegationConfigRead:
    headcount = data.reference_headcount
    if data.initialize_from_current_headcount and headcount is None:
        headcount = count_active_employees(company_id)
    if headcount is None:
        existing = fetch_delegation_config(company_id)
        headcount = int(existing["reference_headcount"]) if existing else count_active_employees(company_id)
    ref_date = data.reference_date or date.today()
    upsert_delegation_config_row(
        company_id=company_id,
        reference_headcount=int(headcount),
        reference_date=ref_date,
        report_enabled=data.report_enabled if data.report_enabled is not None else True,
        mutualisation_enabled=data.mutualisation_enabled
        if data.mutualisation_enabled is not None
        else True,
        created_by=updated_by,
    )
    return get_delegation_config(company_id)


def get_delegation_credit(
    company_id: str, employee_id: str, year: int, month: int
) -> DelegationCreditRead:
    ref_headcount, ref_date, report_enabled, mutua_enabled = _resolve_reference_headcount(
        company_id
    )
    ctx = _mandate_context(company_id, employee_id)
    role = ctx["role"]
    override = ctx["monthly_hours_override"]

    window_start = date(year, month, 1) - timedelta(days=365)
    months = _months_range(window_start.replace(day=1), date(year, month, 1))
    consumed, tin, tout = _load_monthly_data(company_id, employee_id, months)
    balances = compute_rolling_balances(
        role=role,
        reference_headcount=ref_headcount,
        monthly_hours_override=override,
        report_enabled=report_enabled,
        mutualisation_enabled=mutua_enabled,
        monthly_consumed=consumed,
        monthly_transfers_in=tin,
        monthly_transfers_out=tout,
        months=months,
    )
    detail = balances.get((year, month))
    if not detail:
        detail = compute_monthly_balance(
            MonthlyBalanceInput(
                year=year,
                month=month,
                role=role,
                reference_headcount=ref_headcount,
                monthly_hours_override=override,
                report_enabled=report_enabled,
                mutualisation_enabled=mutua_enabled,
            )
        )

    return DelegationCreditRead(
        employee_id=employee_id,
        year=year,
        month=month,
        role=role,
        reference_headcount=ref_headcount,
        reference_date=ref_date,
        credit_base=detail.credit_base,
        reported_available=detail.reported_available,
        transfers_in=detail.transfers_in,
        transfers_out=detail.transfers_out,
        monthly_cap=detail.monthly_cap,
        available_hours=detail.available_hours,
        consumed_hours=detail.consumed_hours,
        remaining_hours=detail.remaining_hours,
        overrun_hours=detail.overrun_hours,
        is_near_limit=detail.is_near_limit,
        is_over_limit=detail.is_over_limit,
        warnings=list(detail.warnings),
        quota_hours_per_month=detail.credit_base,
    )


def get_delegation_quota_computed(
    company_id: str, employee_id: str
) -> Optional[DelegationQuotaRead]:
    """Compatibilité : quota = crédit de base calculé (barème + rôle + override)."""
    today = date.today()
    credit = get_delegation_credit(company_id, employee_id, today.year, today.month)
    ctx = _mandate_context(company_id, employee_id)
    if credit.credit_base <= 0 and ctx["monthly_hours_override"] is None:
        mandate = fetch_active_mandate_with_override(company_id, employee_id)
        if not mandate:
            return None
    config = fetch_delegation_config(company_id)
    return DelegationQuotaRead(
        id=config["id"] if config else employee_id,
        company_id=company_id,
        collective_agreement_id=None,
        quota_hours_per_month=credit.credit_base,
        notes=(
            f"Barème légal R. 2314-1 — effectif réf. {credit.reference_headcount}"
            if credit.reference_headcount
            else "Crédit calculé"
        ),
        collective_agreement_name=None,
        credit_base=credit.credit_base,
        monthly_cap=credit.monthly_cap,
        reference_headcount=credit.reference_headcount,
        role=credit.role,
    )


def get_delegation_summary_enriched(
    company_id: str, period_start: date, period_end: date
) -> List[DelegationSummary]:
    from app.modules.cse.infrastructure.cse_service_impl import get_elected_members

    elected = get_elected_members(company_id, active_only=True)
    summaries: List[DelegationSummary] = []
    ref_year, ref_month = period_end.year, period_end.month

    for member in elected:
        credit = get_delegation_credit(
            company_id, member.employee_id, ref_year, ref_month
        )
        hours = fetch_delegation_hours_raw(
            company_id, member.employee_id, period_start, period_end
        )
        consumed = sum(float(h["duration_hours"]) for h in hours)
        summaries.append(
            DelegationSummary(
                employee_id=member.employee_id,
                first_name=member.first_name,
                last_name=member.last_name,
                quota_hours_per_month=credit.credit_base,
                consumed_hours=round(consumed, 2),
                remaining_hours=credit.remaining_hours,
                period_start=period_start,
                period_end=period_end,
                credit_base=credit.credit_base,
                reported_available=credit.reported_available,
                transfers_in=credit.transfers_in,
                transfers_out=credit.transfers_out,
                monthly_cap=credit.monthly_cap,
                available_hours=credit.available_hours,
                overrun_hours=credit.overrun_hours,
                is_near_limit=credit.is_near_limit,
                is_over_limit=credit.is_over_limit,
                role=credit.role,
            )
        )
    return summaries


def create_delegation_transfer(
    company_id: str, data: DelegationTransferCreate, created_by: str
) -> DelegationTransferRead:
    from_ctx = _mandate_context(company_id, data.from_employee_id)
    to_ctx = _mandate_context(company_id, data.to_employee_id)
    ref_headcount, _, report_enabled, mutua_enabled = _resolve_reference_headcount(company_id)
    if not mutua_enabled:
        raise DelegationValidationError("La mutualisation est désactivée")

    from_base = credit_base(from_ctx["role"], ref_headcount, from_ctx["monthly_hours_override"])
    to_base = credit_base(to_ctx["role"], ref_headcount, to_ctx["monthly_hours_override"])

    to_credit = get_delegation_credit(
        company_id, data.to_employee_id, data.period_year, data.period_month
    )
    usage_date = date(data.period_year, data.period_month, 1)
    ok, warnings = validate_transfer(
        from_role=from_ctx["role"],
        from_credit_base=from_base,
        to_credit_base=to_base,
        hours=data.hours,
        to_month_consumed=to_credit.consumed_hours,
        to_month_transfers_in=to_credit.transfers_in,
        to_month_reported=to_credit.reported_available,
        employer_notified_at=data.employer_notified_at,
        usage_date=usage_date,
    )
    if not ok:
        raise DelegationValidationError(" ; ".join(warnings))

    row = insert_delegation_transfer(
        {
            "company_id": company_id,
            "period_year": data.period_year,
            "period_month": data.period_month,
            "from_employee_id": data.from_employee_id,
            "to_employee_id": data.to_employee_id,
            "hours": str(data.hours),
            "employer_notified_at": data.employer_notified_at.isoformat()
            if data.employer_notified_at
            else None,
            "created_by": created_by,
        }
    )
    return DelegationTransferRead(
        id=row["id"],
        company_id=company_id,
        period_year=data.period_year,
        period_month=data.period_month,
        from_employee_id=data.from_employee_id,
        to_employee_id=data.to_employee_id,
        hours=float(row["hours"]),
        employer_notified_at=data.employer_notified_at,
        warnings=warnings,
        created_at=datetime.fromisoformat(row["created_at"])
        if isinstance(row["created_at"], str)
        else row["created_at"],
    )


def list_delegation_transfers(
    company_id: str,
    employee_id: Optional[str] = None,
    period_year: Optional[int] = None,
    period_month: Optional[int] = None,
) -> List[DelegationTransferRead]:
    rows = fetch_delegation_transfers(company_id, employee_id)
    out: List[DelegationTransferRead] = []
    for row in rows:
        if period_year and int(row["period_year"]) != period_year:
            continue
        if period_month and int(row["period_month"]) != period_month:
            continue
        notified = row.get("employer_notified_at")
        out.append(
            DelegationTransferRead(
                id=row["id"],
                company_id=company_id,
                period_year=int(row["period_year"]),
                period_month=int(row["period_month"]),
                from_employee_id=str(row["from_employee_id"]),
                to_employee_id=str(row["to_employee_id"]),
                hours=float(row["hours"]),
                employer_notified_at=datetime.fromisoformat(notified).date()
                if notified
                else None,
                warnings=[],
                created_at=datetime.fromisoformat(row["created_at"])
                if isinstance(row["created_at"], str)
                else row["created_at"],
            )
        )
    return out


def get_annual_register(company_id: str, year: int) -> List[DelegationRegisterRow]:
    from app.modules.cse.infrastructure.cse_service_impl import get_elected_members

    elected = get_elected_members(company_id, active_only=True)
    months = [(year, m) for m in range(1, 13)]
    rows: List[DelegationRegisterRow] = []
    for member in elected:
        ctx = _mandate_context(company_id, member.employee_id)
        ref_headcount, _, report_enabled, mutua_enabled = _resolve_reference_headcount(
            company_id
        )
        consumed, tin, tout = _load_monthly_data(company_id, member.employee_id, months)
        balances = compute_rolling_balances(
            role=ctx["role"],
            reference_headcount=ref_headcount,
            monthly_hours_override=ctx["monthly_hours_override"],
            report_enabled=report_enabled,
            mutualisation_enabled=mutua_enabled,
            monthly_consumed=consumed,
            monthly_transfers_in=tin,
            monthly_transfers_out=tout,
            months=months,
        )
        reg = annual_register_row(year, balances)
        rows.append(
            DelegationRegisterRow(
                employee_id=member.employee_id,
                first_name=member.first_name,
                last_name=member.last_name,
                year=year,
                role=ctx["role"],
                **reg,
            )
        )
    return rows


def sync_payroll_entry_for_hour(
    company_id: str,
    employee_id: str,
    delegation_hour_id: str,
    usage_date: date,
    duration_hours: float,
    is_overrun: bool,
) -> None:
    """Impute une heure de délégation en paie (rubrique DELEGATION_CSE)."""
    insert_payroll_entry(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "delegation_hour_id": delegation_hour_id,
            "year": usage_date.year,
            "month": usage_date.month,
            "hours": str(duration_hours),
            "is_overrun": is_overrun,
            "rubrique_code": "DELEGATION_CSE",
        }
    )


def enrich_delegation_hour_create(
    company_id: str, employee_id: str, data: DelegationHourCreate
) -> Dict[str, Any]:
    """Prépare l'insertion d'une heure avec source et détection dépassement."""
    credit = get_delegation_credit(
        company_id, employee_id, data.date.year, data.date.month
    )
    projected = credit.consumed_hours + data.duration_hours
    is_overrun = projected > credit.available_hours
    source = data.source or ("exceptionnelle" if is_overrun else "propre")
    return {
        "source": source,
        "origin_month": data.origin_month.isoformat() if data.origin_month else None,
        "is_overrun": is_overrun,
    }


def create_delegation_request(
    company_id: str, data: DelegationRequestCreate, created_by: str
) -> DelegationRequestRead:
    from app.modules.cse.schemas import DelegationRequestRead

    employee_id = data.employee_id or created_by
    row = insert_delegation_request(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "planned_date": data.planned_date.isoformat(),
            "planned_hours": str(data.planned_hours),
            "reason": data.reason,
            "status": "planifie",
            "employer_notified_at": data.employer_notified_at.isoformat()
            if data.employer_notified_at
            else None,
            "created_by": created_by,
        }
    )
    return DelegationRequestRead(
        id=row["id"],
        company_id=company_id,
        employee_id=employee_id,
        planned_date=data.planned_date,
        planned_hours=float(row["planned_hours"]),
        reason=data.reason,
        status="planifie",
        employer_notified_at=data.employer_notified_at,
        created_at=datetime.fromisoformat(row["created_at"])
        if isinstance(row["created_at"], str)
        else row["created_at"],
    )


def update_delegation_request_status(
    company_id: str,
    request_id: str,
    data: DelegationRequestUpdate,
) -> DelegationRequestRead:
    from app.modules.cse.schemas import DelegationRequestRead

    updates: Dict[str, Any] = {}
    if data.status is not None:
        updates["status"] = data.status
    if data.realized_hours is not None:
        updates["realized_hours"] = str(data.realized_hours)
    if data.delegation_hour_id is not None:
        updates["delegation_hour_id"] = data.delegation_hour_id
    row = update_delegation_request(request_id, updates)
    if str(row.get("company_id")) != company_id:
        raise DelegationNotFoundError("Bon de délégation introuvable")
    planned = row.get("planned_date")
    if isinstance(planned, str):
        planned = datetime.fromisoformat(planned).date()
    notified = row.get("employer_notified_at")
    return DelegationRequestRead(
        id=row["id"],
        company_id=company_id,
        employee_id=str(row["employee_id"]),
        planned_date=planned,
        planned_hours=float(row["planned_hours"]),
        reason=row["reason"],
        status=row["status"],
        realized_hours=float(row["realized_hours"])
        if row.get("realized_hours") is not None
        else None,
        employer_notified_at=datetime.fromisoformat(notified).date() if notified else None,
        delegation_hour_id=row.get("delegation_hour_id"),
        created_at=datetime.fromisoformat(row["created_at"])
        if isinstance(row["created_at"], str)
        else row["created_at"],
    )


def get_payroll_delegation_entries(
    company_id: str, year: int, month: int, employee_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Entrées paie heures de délégation pour un mois (rubrique DELEGATION_CSE)."""
    from app.modules.cse.infrastructure.delegation_queries import fetch_payroll_entries

    rows = fetch_payroll_entries(company_id, year, month, employee_id)
    return [
        {
            "employee_id": str(r["employee_id"]),
            "hours": float(r["hours"]),
            "is_overrun": bool(r.get("is_overrun", False)),
            "rubrique_code": r.get("rubrique_code", "DELEGATION_CSE"),
            "delegation_hour_id": r.get("delegation_hour_id"),
        }
        for r in rows
    ]


def list_delegation_requests(
    company_id: str, employee_id: Optional[str] = None
) -> List[DelegationRequestRead]:
    rows = fetch_delegation_requests(company_id, employee_id)
    out: List[DelegationRequestRead] = []
    for row in rows:
        planned = row.get("planned_date")
        if isinstance(planned, str):
            planned = datetime.fromisoformat(planned).date()
        notified = row.get("employer_notified_at")
        out.append(
            DelegationRequestRead(
                id=row["id"],
                company_id=company_id,
                employee_id=str(row["employee_id"]),
                planned_date=planned,
                planned_hours=float(row["planned_hours"]),
                reason=row["reason"],
                status=row["status"],
                realized_hours=float(row["realized_hours"])
                if row.get("realized_hours") is not None
                else None,
                employer_notified_at=datetime.fromisoformat(notified).date()
                if notified
                else None,
                delegation_hour_id=row.get("delegation_hour_id"),
                created_at=datetime.fromisoformat(row["created_at"])
                if isinstance(row["created_at"], str)
                else row["created_at"],
            )
        )
    return out
