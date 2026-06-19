"""Commandes CET — création, validation, ajustements."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.database import supabase
from app.modules.cet.application import notifications as cet_notif
from app.modules.cet.application.queries import (
    build_employee_summary,
    settings_to_api,
)
from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cet_balance_days,
    resolve_initial_workflow,
    validate_account_balance_cap,
    validate_deposit_cp,
    validate_deposit_hours,
    validate_request_deadline,
    validate_withdraw_hours,
)
from app.modules.cet.infrastructure import repository as cet_repo
from app.modules.payroll.application.payslip_commands import is_forfait_jour
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


def _get_settings(company_id: str) -> dict[str, Any]:
    return settings_to_api(cet_repo.get_cet_settings_row(company_id))


def _enforce_deadline(settings: dict[str, Any]) -> None:
    today = date.today()
    validate_request_deadline(today.day, settings.get("request_deadline_day_of_month"))


def _apply_hs_debit_on_validation(movement_id: str, settings: dict[str, Any]) -> None:
    if settings.get("hs_debit_timing") == "on_validation":
        cet_repo.mark_movements_applied_payroll([movement_id])


def _notify_after_creation(
    movement: dict[str, Any],
    settings: dict[str, Any],
    employee_id: str,
    company_id: str,
) -> None:
    movement_type = str(movement.get("movement_type") or "")
    hours = float(movement.get("hours") or 0)
    days = float(movement.get("days") or 0)
    wf = str(movement.get("workflow_step") or "")

    cet_notif.notify_cet_submitted(
        employee_id, company_id, movement_type, hours=hours, days=days
    )
    if wf == "pending_manager":
        mgr = get_team_manager_employee_id(employee_id)
        if mgr:
            cet_notif.notify_manager_new_cet_request(
                mgr, company_id, employee_id, movement_type, hours=hours, days=days
            )


def _build_movement_payload(
    *,
    employee_id: str,
    company_id: str,
    settings: dict[str, Any],
    requested_by: str,
    year: int,
    month: int,
    movement_type: str,
    hours: float | None = None,
    days: float | None = None,
    note: str | None = None,
    force_validated: bool = False,
) -> dict[str, Any]:
    mgr = get_team_manager_employee_id(employee_id)
    if force_validated:
        status, workflow_step = "validated", "approved_rh"
    else:
        status, workflow_step = resolve_initial_workflow(
            settings["validation_mode"], has_manager=bool(mgr)
        )

    payload: dict[str, Any] = {
        "employee_id": employee_id,
        "company_id": company_id,
        "year": year,
        "month": month,
        "movement_type": movement_type,
        "status": status,
        "workflow_step": workflow_step,
        "requested_by": requested_by,
    }
    if hours is not None:
        payload["hours"] = round(hours, 2)
    if days is not None:
        payload["days"] = round(days, 2)
    if note:
        payload["note"] = note
    if status == "validated":
        payload["validated_by"] = requested_by
    return payload


def create_deposit(
    employee_id: str,
    company_id: str,
    hours: float,
    *,
    requested_by: str,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    settings = _get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    if not settings["allow_deposit_hs"]:
        raise ValueError("L'alimentation CET par heures sup n'est pas activée.")
    emp = _get_employee_row(employee_id)
    if not emp or str(emp["company_id"]) != company_id:
        raise LookupError("Employé introuvable.")
    if is_forfait_jour(emp.get("statut")):
        raise ValueError("Le CET n'est pas applicable aux salariés au forfait jour.")

    _enforce_deadline(settings)
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

    payload = _build_movement_payload(
        employee_id=employee_id,
        company_id=company_id,
        settings=settings,
        requested_by=requested_by,
        year=y,
        month=m,
        movement_type="deposit_hs",
        hours=hours,
    )
    movement = cet_repo.insert_movement(payload)
    if movement.get("status") == "validated":
        _apply_hs_debit_on_validation(str(movement["id"]), settings)
    _notify_after_creation(movement, settings, employee_id, company_id)
    return movement


def create_deposit_cp(
    employee_id: str,
    company_id: str,
    days: float,
    *,
    requested_by: str,
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    settings = _get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    if not settings["allow_deposit_cp"]:
        raise ValueError("Le transfert de congés payés vers le CET n'est pas activé.")
    emp = _get_employee_row(employee_id)
    if not emp or str(emp["company_id"]) != company_id:
        raise LookupError("Employé introuvable.")
    if is_forfait_jour(emp.get("statut")):
        raise ValueError("Le CET n'est pas applicable aux salariés au forfait jour.")

    _enforce_deadline(settings)
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

    payload = _build_movement_payload(
        employee_id=employee_id,
        company_id=company_id,
        settings=settings,
        requested_by=requested_by,
        year=y,
        month=m,
        movement_type="deposit_cp",
        days=days,
    )
    movement = cet_repo.insert_movement(payload)
    _notify_after_creation(movement, settings, employee_id, company_id)
    return movement


def create_withdrawal(
    employee_id: str,
    company_id: str,
    hours: float,
    *,
    requested_by: str,
) -> dict[str, Any]:
    settings = _get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    _enforce_deadline(settings)
    summary = build_employee_summary(employee_id)
    validate_withdraw_hours(hours, summary["balance_hours"])

    today = date.today()
    payload = _build_movement_payload(
        employee_id=employee_id,
        company_id=company_id,
        settings=settings,
        requested_by=requested_by,
        year=today.year,
        month=today.month,
        movement_type="withdraw_rest",
        hours=hours,
    )
    movement = cet_repo.insert_movement(payload)
    _notify_after_creation(movement, settings, employee_id, company_id)
    return movement


def _revalidate_movement_business_rules(
    mvt: dict[str, Any], settings: dict[str, Any]
) -> None:
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
        validate_deposit_cp(days, quota_remaining=quota, cp_balance_available=cp_bal)
        all_rows = _movement_rows(cet_repo.list_movements_for_employee(employee_id))
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


def validate_movement(
    movement_id: str,
    company_id: str,
    *,
    approved: bool,
    validated_by: str,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    mvt = cet_repo.get_movement_by_id(movement_id)
    if not mvt or str(mvt.get("company_id")) != company_id:
        raise LookupError("Mouvement introuvable.")
    if mvt.get("status") != "pending":
        raise ValueError("Ce mouvement n'est plus en attente de validation.")
    wf = str(mvt.get("workflow_step") or "pending")
    if wf == "pending_manager":
        raise ValueError(
            "Ce mouvement est encore en attente de validation manager."
        )
    if wf not in ("pending", "approved_manager"):
        raise ValueError("Ce mouvement n'est pas éligible à une validation RH.")

    settings = _get_settings(company_id)
    employee_id = str(mvt["employee_id"])
    movement_type = str(mvt.get("movement_type") or "")
    hours = float(mvt.get("hours") or 0)
    days = float(mvt.get("days") or 0)

    if approved:
        _revalidate_movement_business_rules(mvt, settings)

    status = "validated" if approved else "rejected"
    workflow_step = "approved_rh" if approved else "rejected_rh"
    updated = cet_repo.update_movement(
        movement_id,
        {
            "status": status,
            "workflow_step": workflow_step,
            "validated_by": validated_by,
            "note": rejection_reason if not approved and rejection_reason else mvt.get("note"),
        },
    )
    result = updated or mvt

    if approved and movement_type == "deposit_hs":
        _apply_hs_debit_on_validation(movement_id, settings)

    cet_notif.notify_cet_rh_decision(
        employee_id,
        company_id,
        approved=approved,
        movement_type=movement_type,
        hours=hours,
        days=days,
        reason=rejection_reason,
    )
    return result


def approve_by_manager(
    movement_id: str,
    company_id: str,
    manager_user_id: str,
    *,
    approved: bool,
    rejection_reason: str | None = None,
) -> dict[str, Any]:
    settings = _get_settings(company_id)
    mvt = cet_repo.get_movement_by_id(movement_id)
    if not mvt:
        raise LookupError("Mouvement introuvable.")

    if approved:
        _revalidate_movement_business_rules(mvt, settings)

    updated = cet_repo.approve_by_manager(
        movement_id,
        company_id,
        manager_user_id,
        approved=approved,
        rejection_reason=rejection_reason,
        validation_mode=settings["validation_mode"],
    )

    employee_id = str(updated["employee_id"])
    movement_type = str(updated.get("movement_type") or "")
    hours = float(updated.get("hours") or 0)
    days = float(updated.get("days") or 0)

    cet_notif.notify_cet_manager_decision(
        employee_id,
        company_id,
        approved=approved,
        movement_type=movement_type,
        hours=hours,
        days=days,
        reason=rejection_reason,
    )

    if approved and updated.get("status") == "validated" and movement_type == "deposit_hs":
        _apply_hs_debit_on_validation(movement_id, settings)

    return updated


def create_opening_balance(
    employee_id: str,
    company_id: str,
    hours: float,
    *,
    created_by: str,
    note: str | None = None,
) -> dict[str, Any]:
    settings = _get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    emp = _get_employee_row(employee_id)
    if not emp or str(emp["company_id"]) != company_id:
        raise LookupError("Employé introuvable.")
    if hours <= 0:
        raise ValueError("Le solde initial doit être strictement positif.")

    today = date.today()
    return cet_repo.insert_movement(
        _build_movement_payload(
            employee_id=employee_id,
            company_id=company_id,
            settings=settings,
            requested_by=created_by,
            year=today.year,
            month=today.month,
            movement_type="adjustment",
            hours=hours,
            note=note or "Solde initial CET",
            force_validated=True,
        )
    )


def create_adjustment(
    employee_id: str,
    company_id: str,
    *,
    hours: float | None = None,
    days: float | None = None,
    created_by: str,
    note: str,
) -> dict[str, Any]:
    settings = _get_settings(company_id)
    if not settings["cet_enabled"]:
        raise ValueError("Le CET n'est pas activé pour cette entreprise.")
    emp = _get_employee_row(employee_id)
    if not emp or str(emp["company_id"]) != company_id:
        raise LookupError("Employé introuvable.")
    if (hours is None or hours == 0) and (days is None or days == 0):
        raise ValueError("Indiquez des heures ou des jours pour l'ajustement.")

    today = date.today()
    return cet_repo.insert_movement(
        _build_movement_payload(
            employee_id=employee_id,
            company_id=company_id,
            settings=settings,
            requested_by=created_by,
            year=today.year,
            month=today.month,
            movement_type="adjustment",
            hours=hours or 0,
            days=days or 0,
            note=note,
            force_validated=True,
        )
    )
