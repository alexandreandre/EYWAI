"""Service applicatif CET."""

from __future__ import annotations

import calendar as cal_mod
from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.cet.application.queries import get_cp_balance_available_for_cet
from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cet_balance_days,
    compute_cet_balance_hours,
    compute_cp_transferred_days_year,
    compute_spareable_overtime_hours,
    hours_to_rest_days,
    remaining_cp_transfer_quota,
    validate_account_balance_cap,
    validate_deposit_cp,
    validate_deposit_hours,
    validate_withdraw_hours,
)
from app.modules.cet.infrastructure import repository as cet_repo
from app.modules.payroll.application.payslip_commands import is_forfait_jour
from app.modules.schedules.infrastructure.mappers import (
    extract_calendrier_reel_from_actual_hours,
)
from app.modules.schedules.infrastructure.repository import schedule_repository


def _settings_to_api(row: dict[str, Any]) -> dict[str, Any]:
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
    return _settings_to_api(cet_repo.get_cet_settings_row(company_id))


def update_settings(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    row = cet_repo.upsert_cet_settings(company_id, payload)
    return _settings_to_api(row)


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


def _get_employee_row(employee_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("employees")
        .select("id, company_id, statut, duree_hebdomadaire, first_name, last_name")
        .eq("id", employee_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def _pending_movements_api(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(m["id"]),
            "movement_type": str(m["movement_type"]),
            "hours": float(m.get("hours") or 0),
            "days": float(m.get("days") or 0),
            "status": str(m.get("status") or ""),
            "year": int(m.get("year") or 0),
            "month": int(m.get("month") or 0),
            "created_at": m.get("created_at"),
        }
        for m in raw
        if m.get("status") == "pending"
    ]


def compute_conjonctural_overtime_hours(
    employee_id: str, year: int, month: int
) -> float:
    """HS conjoncturelles du mois à partir du calendrier réel."""
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
        1
        for entry in calendrier_reel
        if entry.get("type") == "conges_payes"
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

    return {
        "employee_id": employee_id,
        "company_id": company_id,
        "cet_enabled": settings["cet_enabled"],
        "eligible": eligible,
        "allow_deposit_hs": settings["allow_deposit_hs"],
        "allow_deposit_cp": settings["allow_deposit_cp"],
        "cp_unit": settings["cp_unit"],
        "year": y,
        "month": m,
        "balance_hours": balance,
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


def create_deposit(
    employee_id: str,
    company_id: str,
    hours: float,
    *,
    requested_by: str,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    settings = get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    if not settings["allow_deposit_hs"]:
        raise ValueError("L'alimentation CET par heures sup n'est pas activée.")
    emp = _get_employee_row(employee_id)
    if not emp or str(emp["company_id"]) != company_id:
        raise LookupError("Employé introuvable.")
    if is_forfait_jour(emp.get("statut")):
        raise ValueError("Le CET n'est pas applicable aux salariés au forfait jour.")

    today = date.today()
    y = year or today.year
    m = month or today.month
    summary = build_employee_summary(employee_id, year=y, month=m)
    validate_deposit_hours(hours, summary["spareable_hours"])

    all_rows = _movement_rows(cet_repo.list_movements_for_employee(employee_id))
    validate_account_balance_cap(
        hours / settings["hours_per_rest_day"],
        compute_cet_balance_days(all_rows, hours_per_rest_day=settings["hours_per_rest_day"]),
        settings["max_account_balance_days"],
    )

    status = "validated" if settings["validation_mode"] == "auto" else "pending"
    return cet_repo.insert_movement(
        {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": y,
            "month": m,
            "movement_type": "deposit_hs",
            "hours": round(hours, 2),
            "status": status,
            "requested_by": requested_by,
            "validated_by": requested_by if status == "validated" else None,
        }
    )


def create_deposit_cp(
    employee_id: str,
    company_id: str,
    days: float,
    *,
    requested_by: str,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    settings = get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    if not settings["allow_deposit_cp"]:
        raise ValueError("Le transfert de congés payés vers le CET n'est pas activé.")
    emp = _get_employee_row(employee_id)
    if not emp or str(emp["company_id"]) != company_id:
        raise LookupError("Employé introuvable.")
    if is_forfait_jour(emp.get("statut")):
        raise ValueError("Le CET n'est pas applicable aux salariés au forfait jour.")

    today = date.today()
    y = year or today.year
    m = month or today.month
    summary = build_employee_summary(employee_id, year=y, month=m)

    validate_deposit_cp(
        days,
        quota_remaining=summary["cp_transfer_remaining_days"],
        cp_balance_available=summary["cp_balance_available"],
    )

    all_rows = _movement_rows(cet_repo.list_movements_for_employee(employee_id))
    validate_account_balance_cap(
        days,
        compute_cet_balance_days(all_rows, hours_per_rest_day=settings["hours_per_rest_day"]),
        settings["max_account_balance_days"],
    )

    status = "validated" if settings["validation_mode"] == "auto" else "pending"
    return cet_repo.insert_movement(
        {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": y,
            "month": m,
            "movement_type": "deposit_cp",
            "days": round(days, 2),
            "status": status,
            "requested_by": requested_by,
            "validated_by": requested_by if status == "validated" else None,
        }
    )


def create_withdrawal(
    employee_id: str,
    company_id: str,
    hours: float,
    *,
    requested_by: str,
) -> dict[str, Any]:
    settings = get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    summary = build_employee_summary(employee_id)
    validate_withdraw_hours(hours, summary["balance_hours"])

    today = date.today()
    status = "validated" if settings["validation_mode"] == "auto" else "pending"
    return cet_repo.insert_movement(
        {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": today.year,
            "month": today.month,
            "movement_type": "withdraw_rest",
            "hours": round(hours, 2),
            "status": status,
            "requested_by": requested_by,
            "validated_by": requested_by if status == "validated" else None,
        }
    )


def validate_movement(
    movement_id: str,
    company_id: str,
    *,
    approved: bool,
    validated_by: str,
) -> dict[str, Any]:
    mvt = cet_repo.get_movement_by_id(movement_id)
    if not mvt or str(mvt.get("company_id")) != company_id:
        raise LookupError("Mouvement introuvable.")
    if mvt.get("status") != "pending":
        raise ValueError("Ce mouvement n'est plus en attente de validation.")

    if approved:
        settings = get_settings(company_id)
        employee_id = str(mvt["employee_id"])
        movement_type = str(mvt.get("movement_type") or "")
        if movement_type == "deposit_cp":
            days = float(mvt.get("days") or 0)
            summary = build_employee_summary(
                employee_id, year=int(mvt.get("year") or date.today().year)
            )
            quota = summary["cp_transfer_remaining_days"]
            if quota is not None:
                quota = round(quota + days, 2)
            cp_bal = round(summary["cp_balance_available"] + days, 2)
            validate_deposit_cp(
                days,
                quota_remaining=quota,
                cp_balance_available=cp_bal,
            )
            all_rows = _movement_rows(
                cet_repo.list_movements_for_employee(employee_id)
            )
            validate_account_balance_cap(
                days,
                compute_cet_balance_days(
                    all_rows, hours_per_rest_day=settings["hours_per_rest_day"]
                ),
                settings["max_account_balance_days"],
            )
        elif movement_type == "deposit_hs":
            hours = float(mvt.get("hours") or 0)
            summary = build_employee_summary(
                employee_id,
                year=int(mvt.get("year") or date.today().year),
                month=int(mvt.get("month") or date.today().month),
            )
            validate_deposit_hours(hours, summary["spareable_hours"] + hours)

    status = "validated" if approved else "rejected"
    updated = cet_repo.update_movement(
        movement_id,
        {"status": status, "validated_by": validated_by},
    )
    return updated or mvt
