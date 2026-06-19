"""Requêtes CET — soldes, synthèses, suivi entreprise."""

from __future__ import annotations

import calendar as cal_mod
from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.absences.application.queries import (
    _leave_context,
    _parse_hire_date,
)
from app.modules.absences.domain.rules import get_available_conge_paye_days
from app.modules.absences.infrastructure.repository import absence_repository
from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cet_balance_days,
    compute_cet_balance_hours,
    compute_cp_transferred_days_year,
    compute_running_balance_days,
    compute_cp_days_committed_for_absences,
    compute_spareable_overtime_hours,
    convert_cp_days_between_units,
    hours_to_rest_days,
    remaining_cp_transfer_quota,
    HOURS_PER_REST_DAY_DEFAULT,
    OUVRES_TO_OUVRABLES_DEFAULT,
)
from app.modules.cet.infrastructure import repository as cet_repo
from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_reel_from_actual_hours,
)
from app.modules.schedules.infrastructure.repository import schedule_repository
from app.shared.team_manager import get_team_manager_employee_id


def _movement_rows(raw: list[dict[str, Any]]) -> list[CetMovementRow]:
    return [
        CetMovementRow(
            movement_type=str(m["movement_type"]),
            hours=float(m.get("hours") or 0),
            status=str(m.get("status") or ""),
            days=float(m.get("days") or 0),
            year=int(m.get("year") or 0),
        )
        for m in raw
    ]


def _get_employee_company_id(employee_id: str) -> str | None:
    resp = (
        supabase.table("employees")
        .select("company_id")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return str(rows[0]["company_id"]) if rows else None


def _read_settings(company_id: str) -> dict[str, Any]:
    row = cet_repo.get_cet_settings_row(company_id)
    return {
        "cet_enabled": bool(row.get("cet_enabled")),
        "allow_deposit_cp": bool(row.get("allow_deposit_cp")),
        "cp_unit": row.get("cp_unit") or "ouvrables",
        "ouvres_to_ouvrables_ratio": float(
            row.get("ouvres_to_ouvrables_ratio") or OUVRES_TO_OUVRABLES_DEFAULT
        ),
        "cp_debit_timing": row.get("cp_debit_timing") or "on_validation",
        "hours_per_rest_day": float(row.get("hours_per_rest_day") or HOURS_PER_REST_DAY_DEFAULT),
    }


def get_cet_cp_committed_days(
    employee_id: str,
    year: int,
    *,
    company_id: str | None = None,
) -> float:
    """Jours CP engagés via CET (selon timing débit entreprise), en unité accord CET."""
    emp_company = company_id or _get_employee_company_id(employee_id)
    if not emp_company:
        return 0.0
    settings = _read_settings(emp_company)
    movements = cet_repo.list_movements_for_employee(employee_id, year=year)
    rows = _movement_rows(movements)
    return compute_cp_days_committed_for_absences(
        rows,
        year,
        cp_debit_timing=settings["cp_debit_timing"],
    )


def get_cp_balance_available_for_cet(
    employee_id: str,
    ref_date: date | None = None,
) -> float:
    """
    Solde CP disponible pour un transfert CET, dans l'unité paramétrée (ouvres/ouvrables).
    """
    ref = ref_date or date.today()
    hire_date = _parse_hire_date(employee_id)
    if not hire_date:
        return 0.0

    company_id = _get_employee_company_id(employee_id)
    if not company_id:
        return 0.0
    settings = _read_settings(company_id)
    if not settings["allow_deposit_cp"]:
        return 0.0

    cp_unit = settings["cp_unit"]
    ratio = settings["ouvres_to_ouvrables_ratio"]
    requests = absence_repository.list_by_employee_id(employee_id)
    policy, adjustment, _, cp_seniority = _leave_context(employee_id, ref.year, company_id)
    from app.modules.absences.application.queries import _cp_balance_extras

    extras = _cp_balance_extras(employee_id, ref, company_id, policy, cp_seniority)
    raw_available = get_available_conge_paye_days(
        hire_date,
        requests,
        ref,
        policy=policy,
        adjustment=adjustment,
        **extras,
    )
    available_in_cet_unit = convert_cp_days_between_units(
        raw_available,
        "ouvrables",
        cp_unit,
        ratio,
    )
    cet_committed = get_cet_cp_committed_days(
        employee_id, ref.year, company_id=company_id
    )
    return round(max(0.0, available_in_cet_unit - cet_committed), 2)


def get_cet_cp_extra_committed_for_absences(
    employee_id: str,
    year: int,
) -> float:
    """Jours CP CET à soustraire du solde absences (unité ouvrables)."""
    company_id = _get_employee_company_id(employee_id)
    if not company_id:
        return 0.0
    settings = _read_settings(company_id)
    if not settings["cet_enabled"] or not settings["allow_deposit_cp"]:
        return 0.0

    cp_unit = settings["cp_unit"]
    ratio = settings["ouvres_to_ouvrables_ratio"]
    movements = cet_repo.list_movements_for_employee(employee_id, year=year)
    rows = _movement_rows(movements)
    committed_cet_unit = compute_cp_days_committed_for_absences(
        rows,
        year,
        cp_debit_timing=settings["cp_debit_timing"],
    )
    return convert_cp_days_between_units(
        committed_cet_unit,
        cp_unit,
        "ouvrables",
        ratio,
    )


def settings_to_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "company_id": str(row["company_id"]),
        "cet_enabled": bool(row.get("cet_enabled")),
        "agreement_reference": row.get("agreement_reference"),
        "hours_per_rest_day": float(row.get("hours_per_rest_day") or 7),
        "request_deadline_day_of_month": row.get("request_deadline_day_of_month"),
        "validation_mode": row.get("validation_mode") or "rh",
        "allow_deposit_hs": bool(row.get("allow_deposit_hs", True)),
        "allow_deposit_cp": bool(row.get("allow_deposit_cp", False)),
        "max_cp_days_per_year": (
            float(row["max_cp_days_per_year"])
            if row.get("max_cp_days_per_year") is not None
            else None
        ),
        "max_account_balance_days": (
            float(row["max_account_balance_days"])
            if row.get("max_account_balance_days") is not None
            else None
        ),
        "cp_unit": row.get("cp_unit") or "ouvrables",
        "ouvres_to_ouvrables_ratio": float(
            row.get("ouvres_to_ouvrables_ratio") or 1.2
        ),
        "cp_debit_timing": row.get("cp_debit_timing") or "on_validation",
        "hs_debit_timing": row.get("hs_debit_timing") or "on_payroll",
    }


def get_settings(company_id: str) -> dict[str, Any]:
    return settings_to_api(cet_repo.get_cet_settings_row(company_id))


def _get_employee_row(employee_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("employees")
        .select("id, company_id, statut, duree_hebdomadaire, first_name, last_name, team_id")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _movement_to_api(m: dict[str, Any], *, balance_after_days: float | None = None) -> dict[str, Any]:
    return {
        "id": str(m["id"]),
        "employee_id": str(m["employee_id"]),
        "movement_type": str(m["movement_type"]),
        "hours": float(m.get("hours") or 0),
        "days": float(m.get("days") or 0),
        "status": str(m.get("status") or ""),
        "workflow_step": str(m.get("workflow_step") or "pending"),
        "year": int(m.get("year") or 0),
        "month": int(m.get("month") or 0),
        "note": m.get("note"),
        "created_at": m.get("created_at"),
        "balance_after_days": balance_after_days,
    }


def _pending_movements_api(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _movement_to_api(m)
        for m in raw
        if m.get("status") == "pending"
    ]


def compute_conjonctural_overtime_hours(
    employee_id: str, year: int, month: int
) -> float:
    emp = _get_employee_row(employee_id)
    if not emp:
        return 0.0
    duree_hebdo = float(emp.get("duree_hebdomadaire") or 35)
    days_in_month = cal_mod.monthrange(year, month)[1]

    actual_raw = schedule_repository.get_actual_hours(employee_id, year, month)
    calendrier_reel = extract_calendrier_reel_from_actual_hours(actual_raw)

    jours_ouvrables = sum(
        1
        for j in range(1, days_in_month + 1)
        if date(year, month, j).weekday() < 5
    )
    heures_theoriques = jours_ouvrables * (duree_hebdo / 5)
    jours_cp = sum(
        1 for entry in calendrier_reel if entry.get("type") == "conges_payes"
    )
    heures_dues = heures_theoriques - (jours_cp * (duree_hebdo / 5))
    heures_travaillees = sum(
        float(entry.get("heures_faites") or entry.get("heures") or 0)
        for entry in calendrier_reel
        if entry.get("type") == "travail"
    )
    return round(max(0.0, heures_travaillees - heures_dues), 2)


def build_employee_summary(
    employee_id: str,
    *,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    emp = _get_employee_row(employee_id)
    if not emp:
        raise LookupError("Employé introuvable.")
    company_id = str(emp["company_id"])
    settings = get_settings(company_id)
    today = date.today()
    y = year or today.year
    m = month or today.month

    eligible = settings["cet_enabled"] and not is_forfait_jour(emp.get("statut"))
    all_movements = cet_repo.list_movements_for_employee(employee_id)
    year_movements = cet_repo.list_movements_for_employee(employee_id, year=y)
    month_movements = cet_repo.list_movements_for_employee(employee_id, year=y, month=m)
    rows_all = _movement_rows(all_movements)
    rows_year = _movement_rows(year_movements)
    hprd = settings["hours_per_rest_day"]
    balance = compute_cet_balance_hours(rows_all, hours_per_rest_day=hprd)

    overtime = compute_conjonctural_overtime_hours(employee_id, y, m) if eligible else 0.0
    spareable = (
        compute_spareable_overtime_hours(overtime, _movement_rows(month_movements))
        if eligible and settings["allow_deposit_hs"]
        else 0.0
    )

    cp_transferred = compute_cp_transferred_days_year(rows_year, y)
    cp_quota_remaining = remaining_cp_transfer_quota(
        settings["max_cp_days_per_year"], cp_transferred
    )
    cp_balance_available = (
        get_cp_balance_available_for_cet(employee_id, today)
        if eligible and settings["allow_deposit_cp"]
        else 0.0
    )
    has_manager = bool(get_team_manager_employee_id(employee_id))

    return {
        "employee_id": employee_id,
        "company_id": company_id,
        "cet_enabled": settings["cet_enabled"],
        "eligible": eligible,
        "has_manager": has_manager,
        "allow_deposit_hs": settings["allow_deposit_hs"],
        "allow_deposit_cp": settings["allow_deposit_cp"],
        "cp_unit": settings["cp_unit"],
        "year": y,
        "month": m,
        "balance_hours": balance,
        "balance_days": compute_cet_balance_days(rows_all, hours_per_rest_day=hprd),
        "overtime_hours_month": overtime,
        "spareable_hours": spareable,
        "rest_days_available": hours_to_rest_days(balance, hprd),
        "hours_per_rest_day": hprd,
        "cp_transfer_used_days": cp_transferred,
        "cp_transfer_remaining_days": cp_quota_remaining,
        "cp_balance_available": cp_balance_available,
        "pending_movements": _pending_movements_api(all_movements),
        "settings": settings,
    }


def list_employee_movements(
    employee_id: str,
    *,
    year: int | None = None,
) -> list[dict[str, Any]]:
    settings_row = cet_repo.get_cet_settings_row(
        str(_get_employee_company_id(employee_id) or "")
    )
    hprd = float(settings_row.get("hours_per_rest_day") or HOURS_PER_REST_DAY_DEFAULT)
    raw = cet_repo.list_movements_for_employee(employee_id, year=year, ascending=True)
    rows = _movement_rows(raw)
    balances = compute_running_balance_days(rows, hours_per_rest_day=hprd)
    return [
        _movement_to_api(m, balance_after_days=balances[i] if i < len(balances) else None)
        for i, m in enumerate(raw)
    ]


def get_cet_overview(company_id: str, year: int | None = None) -> list[dict[str, Any]]:
    ref_year = year or date.today().year
    settings = get_settings(company_id)
    if not settings["cet_enabled"]:
        return []

    emp_resp = (
        supabase.table("employees")
        .select("id, first_name, last_name, statut, team_id")
        .eq("company_id", company_id)
        .in_("employment_status", ["actif", "active"])
        .execute()
    )
    overview: list[dict[str, Any]] = []
    for emp in emp_resp.data or []:
        employee_id = str(emp["id"])
        if is_forfait_jour(emp.get("statut")):
            continue
        try:
            summary = build_employee_summary(employee_id, year=ref_year)
        except LookupError:
            continue
        movements = cet_repo.list_movements_for_employee(employee_id)
        pending_count = sum(1 for m in movements if m.get("status") == "pending")
        last_at = movements[0].get("created_at") if movements else None
        overview.append(
            {
                "employee_id": employee_id,
                "first_name": emp.get("first_name") or "",
                "last_name": emp.get("last_name") or "",
                "balance_hours": summary["balance_hours"],
                "balance_days": summary["balance_days"],
                "cp_transfer_used_days": summary["cp_transfer_used_days"],
                "cp_transfer_remaining_days": summary["cp_transfer_remaining_days"],
                "pending_count": pending_count,
                "has_manager": summary["has_manager"],
                "last_movement_at": last_at,
            }
        )
    overview.sort(key=lambda r: (r["last_name"], r["first_name"]))
    return overview


def list_company_pending(company_id: str) -> list[dict[str, Any]]:
    raw = cet_repo.list_pending_movements_for_company(
        company_id, exclude_manager_queue=True
    )
    return [_movement_to_api(m) for m in raw]


def list_pending_manager_approval(company_id: str) -> list[dict[str, Any]]:
    raw = cet_repo.get_pending_manager_approval(company_id)
    result = []
    for m in raw:
        item = _movement_to_api(m)
        emp = m.get("employee") or {}
        item["employee"] = {
            "id": str(emp.get("id") or m.get("employee_id")),
            "first_name": emp.get("first_name") or "",
            "last_name": emp.get("last_name") or "",
        }
        result.append(item)
    return result


def count_company_pending(company_id: str) -> int:
    return cet_repo.count_pending_for_company(company_id)
