"""
Repository CET et paramètres entreprise.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.cet.domain.rules import (
    HOURS_PER_REST_DAY_DEFAULT,
    OUVRES_TO_OUVRABLES_DEFAULT,
)


def _default_cet_settings(company_id: str) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "cet_enabled": False,
        "agreement_reference": None,
        "hours_per_rest_day": HOURS_PER_REST_DAY_DEFAULT,
        "request_deadline_day_of_month": None,
        "validation_mode": "rh",
        "allow_deposit_hs": True,
        "allow_deposit_cp": False,
        "max_cp_days_per_year": None,
        "max_account_balance_days": None,
        "cp_unit": "ouvrables",
        "ouvres_to_ouvrables_ratio": OUVRES_TO_OUVRABLES_DEFAULT,
        "cp_debit_timing": "on_validation",
        "hs_debit_timing": "on_payroll",
    }


def get_cet_settings_row(company_id: str) -> dict[str, Any]:
    resp = (
        supabase.table("company_cet_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    if not rows:
        return _default_cet_settings(company_id)
    return {**_default_cet_settings(company_id), **rows[0]}


def is_cet_enabled(company_id: str) -> bool:
    row = get_cet_settings_row(company_id)
    return bool(row.get("cet_enabled"))


def upsert_cet_settings(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row: dict[str, Any] = {"company_id": company_id, "updated_at": now}
    allowed = (
        "cet_enabled",
        "agreement_reference",
        "hours_per_rest_day",
        "request_deadline_day_of_month",
        "validation_mode",
        "allow_deposit_hs",
        "allow_deposit_cp",
        "max_cp_days_per_year",
        "max_account_balance_days",
        "cp_unit",
        "ouvres_to_ouvrables_ratio",
        "cp_debit_timing",
        "hs_debit_timing",
    )
    for key in allowed:
        if key in payload:
            row[key] = payload[key]

    existing = (
        supabase.table("company_cet_settings")
        .select("id")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        supabase.table("company_cet_settings").update(row).eq(
            "company_id", company_id
        ).execute()
    else:
        row["created_at"] = now
        supabase.table("company_cet_settings").insert(row).execute()
    return get_cet_settings_row(company_id)


def list_movements_for_employee(
    employee_id: str,
    *,
    year: int | None = None,
    month: int | None = None,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    q = (
        supabase.table("employee_cet_movements")
        .select("*")
        .eq("employee_id", employee_id)
        .order("created_at", desc=not ascending)
    )
    if year is not None:
        q = q.eq("year", year)
    if month is not None:
        q = q.eq("month", month)
    resp = q.execute()
    return list(resp.data or [])


def list_pending_movements_for_company(
    company_id: str,
    *,
    exclude_manager_queue: bool = True,
) -> list[dict[str, Any]]:
    q = (
        supabase.table("employee_cet_movements")
        .select(
            "*, employee:employees!employee_cet_movements_employee_id_fkey(id, first_name, last_name)"
        )
        .eq("company_id", company_id)
        .eq("status", "pending")
        .order("created_at", desc=True)
    )
    if exclude_manager_queue:
        q = q.neq("workflow_step", "pending_manager")
    resp = q.execute()
    return list(resp.data or [])


def get_pending_manager_approval(company_id: str) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_cet_movements")
        .select(
            "*, employee:employees!employee_cet_movements_employee_id_fkey(id, first_name, last_name)"
        )
        .eq("company_id", company_id)
        .eq("workflow_step", "pending_manager")
        .eq("status", "pending")
        .order("created_at", desc=True)
        .execute()
    )
    return list(resp.data or [])


def count_pending_for_company(company_id: str) -> int:
    resp = (
        supabase.table("employee_cet_movements")
        .select("id", count="exact")
        .eq("company_id", company_id)
        .eq("status", "pending")
        .execute()
    )
    return int(resp.count or 0)


def get_movement_by_id(movement_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("employee_cet_movements")
        .select("*")
        .eq("id", movement_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def insert_movement(row: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    row = {
        **row,
        "workflow_step": row.get("workflow_step") or "pending",
        "created_at": now,
        "updated_at": now,
    }
    resp = supabase.table("employee_cet_movements").insert(row).execute()
    data = resp.data or []
    return data[0] if data else row


def update_movement(movement_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    updates = {**updates, "updated_at": datetime.now(timezone.utc).isoformat()}
    supabase.table("employee_cet_movements").update(updates).eq("id", movement_id).execute()
    return get_movement_by_id(movement_id)


def _resolve_employee_id_for_user(user_id: str, company_id: str) -> str | None:
    from app.shared.employee_resolution import resolve_employee_id_for_user_account

    return resolve_employee_id_for_user_account(user_id, company_id)


def approve_by_manager(
    movement_id: str,
    company_id: str,
    manager_user_id: str,
    *,
    approved: bool,
    rejection_reason: str | None,
    validation_mode: str,
) -> dict[str, Any]:
    mvt = get_movement_by_id(movement_id)
    if not mvt:
        raise LookupError("Mouvement introuvable.")
    if str(mvt.get("company_id") or "") != str(company_id):
        raise LookupError("Mouvement introuvable pour cette entreprise.")
    if mvt.get("workflow_step") != "pending_manager":
        raise ValueError("Ce mouvement n'est pas en attente de validation manager.")
    if mvt.get("status") != "pending":
        raise ValueError("Ce mouvement n'est plus en attente.")

    now_iso = datetime.now(timezone.utc).isoformat()
    manager_employee_id = _resolve_employee_id_for_user(manager_user_id, company_id)

    if approved:
        if validation_mode == "manager":
            updates: dict[str, Any] = {
                "workflow_step": "approved_manager",
                "status": "validated",
                "manager_approved_at": now_iso,
            }
        else:
            updates = {
                "workflow_step": "approved_manager",
                "status": "pending",
                "manager_approved_at": now_iso,
            }
        if manager_employee_id:
            updates["manager_id"] = manager_employee_id
    else:
        updates = {
            "workflow_step": "rejected_manager",
            "status": "rejected",
            "manager_rejected_at": now_iso,
            "manager_rejection_reason": rejection_reason,
        }
        if manager_employee_id:
            updates["manager_id"] = manager_employee_id

    updated = update_movement(movement_id, updates)
    if not updated:
        raise RuntimeError("Échec de la mise à jour du mouvement.")
    return updated


def mark_movements_applied_payroll(movement_ids: list[str]) -> None:
    if not movement_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    for mid in movement_ids:
        supabase.table("employee_cet_movements").update(
            {"status": "applied_payroll", "updated_at": now}
        ).eq("id", mid).execute()


def get_validated_deposit_hours_for_payroll(
    employee_id: str, year: int, month: int
) -> tuple[float, list[str]]:
    """Retourne (total heures, ids mouvements) pour dépôts validés non encore appliqués."""
    resp = (
        supabase.table("employee_cet_movements")
        .select("id, hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("movement_type", "deposit_hs")
        .eq("status", "validated")
        .execute()
    )
    rows = resp.data or []
    total = sum(float(r.get("hours") or 0) for r in rows)
    ids = [str(r["id"]) for r in rows]
    return round(total, 2), ids


def get_validated_deposit_cp_for_payroll(
    employee_id: str, year: int, month: int
) -> tuple[float, list[str]]:
    """Retourne (total jours CP, ids) pour dépôts CP validés non encore appliqués en paie."""
    resp = (
        supabase.table("employee_cet_movements")
        .select("id, days")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("movement_type", "deposit_cp")
        .eq("status", "validated")
        .execute()
    )
    rows = resp.data or []
    total = sum(float(r.get("days") or 0) for r in rows)
    ids = [str(r["id"]) for r in rows]
    return round(total, 2), ids


def get_validated_withdrawals_for_payroll(
    employee_id: str, year: int, month: int
) -> tuple[float, list[str]]:
    """Retourne (total heures retrait, ids) pour retraits validés non appliqués."""
    resp = (
        supabase.table("employee_cet_movements")
        .select("id, hours")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .eq("month", month)
        .eq("movement_type", "withdraw_rest")
        .eq("status", "validated")
        .execute()
    )
    rows = resp.data or []
    total = sum(float(r.get("hours") or 0) for r in rows)
    ids = [str(r["id"]) for r in rows]
    return round(total, 2), ids
