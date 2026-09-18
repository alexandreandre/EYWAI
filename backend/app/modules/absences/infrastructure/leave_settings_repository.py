"""Repository paramètres congés / RTT et ajustements salarié."""

from __future__ import annotations

import dataclasses
from datetime import date, datetime, timezone
from typing import Any

from app.core.database import supabase
from app.modules.absences.domain.jtc import (
    JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT,
    JTC_ABSENCE_TYPES_DEFAULT,
    JTC_ANNUAL_DAYS_DEFAULT,
)
from app.modules.absences.domain.leave_policy import (
    DEFAULT_LEAVE_POLICY,
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
    RTT_FORFAIT_ANNUAL_DAYS_DEFAULT,
    RTT_FORFAIT_CP_OUVRES_DEDUCTION_DEFAULT,
)


def _row_to_policy(row: dict[str, Any] | None) -> LeavePolicySettings:
    if not row:
        return DEFAULT_LEAVE_POLICY
    max_days = row.get("cp_carryover_max_days")
    rtt_days = row.get("rtt_annual_days")
    return LeavePolicySettings(
        cp_acquisition_days_per_month=float(
            row.get("cp_acquisition_days_per_month") or 2.5
        ),
        cp_counting_unit=str(row.get("cp_counting_unit") or "ouvrable"),  # type: ignore[arg-type]
        cp_reference_period_start_month=int(
            row.get("cp_reference_period_start_month") or 6
        ),
        cp_carryover_enabled=bool(row.get("cp_carryover_enabled", False)),
        cp_carryover_max_days=float(max_days) if max_days is not None else None,
        rtt_annual_days=float(rtt_days) if rtt_days is not None else None,
        rtt_use_calendar_formula=bool(row.get("rtt_use_calendar_formula", False)),
        rtt_use_forfait_jours_formula=bool(
            row.get("rtt_use_forfait_jours_formula", False)
        ),
        rtt_forfait_annual_days=int(
            row.get("rtt_forfait_annual_days") or RTT_FORFAIT_ANNUAL_DAYS_DEFAULT
        ),
        rtt_forfait_cp_ouvres_deduction=float(
            row.get("rtt_forfait_cp_ouvres_deduction")
            or RTT_FORFAIT_CP_OUVRES_DEDUCTION_DEFAULT
        ),
        rtt_forfait_cadres_only=bool(row.get("rtt_forfait_cadres_only", True)),
        rtt_period_start_month=int(row.get("rtt_period_start_month") or 1),
        rtt_period_end_month=int(row.get("rtt_period_end_month") or 12),
        rtt_carryover_enabled=bool(row.get("rtt_carryover_enabled", False)),
        rtt_year_end_reminder_enabled=bool(
            row.get("rtt_year_end_reminder_enabled", False)
        ),
        rtt_year_end_reminder_days_before=int(
            row.get("rtt_year_end_reminder_days_before") or 15
        ),
        jtc_enabled=bool(row.get("jtc_enabled", False)),
        jtc_annual_days=int(row.get("jtc_annual_days") or JTC_ANNUAL_DAYS_DEFAULT),
        jtc_absence_threshold_days=int(
            row.get("jtc_absence_threshold_days")
            or JTC_ABSENCE_THRESHOLD_DAYS_DEFAULT
        ),
        jtc_absence_types=tuple(
            row.get("jtc_absence_types") or JTC_ABSENCE_TYPES_DEFAULT
        ),
    )


def _date_de_reference(row: dict[str, Any]) -> date | None:
    brut = row.get("cp_opening_reference_date")
    if not brut:
        return None
    try:
        return date.fromisoformat(str(brut)[:10])
    except ValueError:
        return None


def _row_to_adjustment(row: dict[str, Any] | None) -> EmployeeLeaveAdjustment:
    if not row:
        return EmployeeLeaveAdjustment.empty()
    forfeited_at = row.get("rtt_forfeited_at")
    return EmployeeLeaveAdjustment(
        cp_n1_opening_balance=float(row.get("cp_n1_opening_balance") or 0),
        cp_n_opening_balance=float(row.get("cp_n_opening_balance") or 0),
        rtt_opening_balance=float(row.get("rtt_opening_balance") or 0),
        rtt_forfeited_at=str(forfeited_at) if forfeited_at else None,
        rtt_forfeited_days=float(row.get("rtt_forfeited_days") or 0),
        jtc_opening_balance=float(row.get("jtc_opening_balance") or 0),
        note=row.get("note"),
        cp_opening_reference_date=_date_de_reference(row),
    )


def resoudre_ajustement_applicable(
    rows: list[dict[str, Any]], year: int
) -> EmployeeLeaveAdjustment:
    """L'ajustement qui vaut pour une année, parmi les lignes du salarié.

    La ligne de l'année s'applique telle quelle. Mais une reprise de soldes est
    datée et calibre les deux périodes de congés qu'elle touche, qui chevauchent
    deux années civiles : ses écarts CP suivent donc les années suivantes tant
    qu'aucune reprise plus récente ne les remplace — sinon ils disparaissaient au
    1er janvier au milieu de la période (Bugny, Colorplast : 28 → 3 jours de N-1
    entre décembre 2026 et janvier 2027). Les compteurs annuels (RTT, JTC) et la
    note, qui pilote le mode « fidèle au bulletin », restent ceux de l'année.
    """
    candidates = [r for r in rows if int(r.get("year") or 0) <= year]
    de_l_annee = next((r for r in candidates if int(r["year"]) == year), None)
    base = _row_to_adjustment(de_l_annee)
    if de_l_annee is not None and base.cp_opening_reference_date is not None:
        return base
    datees = [r for r in candidates if _date_de_reference(r) is not None]
    if not datees:
        return base
    reprise = _row_to_adjustment(max(datees, key=_date_de_reference))
    return dataclasses.replace(
        base,
        cp_n1_opening_balance=reprise.cp_n1_opening_balance,
        cp_n_opening_balance=reprise.cp_n_opening_balance,
        cp_opening_reference_date=reprise.cp_opening_reference_date,
    )


def get_applicable_adjustment(employee_id: str, year: int) -> EmployeeLeaveAdjustment:
    """Ajustement applicable au calcul des soldes d'une année (reprise datée
    des années précédentes comprise). L'écran de saisie, lui, lit la ligne de
    l'année : `get_employee_adjustment`."""
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .eq("employee_id", employee_id)
        .lte("year", year)
        .execute()
    )
    return resoudre_ajustement_applicable(resp.data or [], year)


def get_applicable_adjustments_by_employees(
    employee_ids: list[str], year: int
) -> dict[str, EmployeeLeaveAdjustment]:
    if not employee_ids:
        return {}
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .in_("employee_id", employee_ids)
        .lte("year", year)
        .execute()
    )
    par_salarie: dict[str, list[dict[str, Any]]] = {}
    for row in resp.data or []:
        par_salarie.setdefault(str(row["employee_id"]), []).append(row)
    return {
        eid: resoudre_ajustement_applicable(lignes, year)
        for eid, lignes in par_salarie.items()
    }


def get_leave_policy(company_id: str) -> LeavePolicySettings:
    resp = (
        supabase.table("company_leave_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_policy(rows[0] if rows else None)


def get_leave_policy_row(company_id: str) -> dict[str, Any] | None:
    resp = (
        supabase.table("company_leave_settings")
        .select("*")
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


def upsert_leave_policy(company_id: str, data: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    existing = get_leave_policy_row(company_id)
    payload = {**data, "company_id": company_id, "updated_at": now}
    if existing:
        resp = (
            supabase.table("company_leave_settings")
            .update(payload)
            .eq("company_id", company_id)
            .execute()
        )
    else:
        payload["created_at"] = now
        resp = supabase.table("company_leave_settings").insert(payload).execute()
    if not resp.data:
        raise RuntimeError("Upsert company_leave_settings sans données retournées")
    return resp.data[0] if isinstance(resp.data, list) else resp.data


def get_employee_adjustment(
    employee_id: str, year: int
) -> EmployeeLeaveAdjustment:
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return _row_to_adjustment(rows[0] if rows else None)


def get_adjustments_by_employees_year(
    employee_ids: list[str], year: int
) -> dict[str, EmployeeLeaveAdjustment]:
    if not employee_ids:
        return {}
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .in_("employee_id", employee_ids)
        .eq("year", year)
        .execute()
    )
    result: dict[str, EmployeeLeaveAdjustment] = {}
    for row in resp.data or []:
        eid = str(row["employee_id"])
        result[eid] = _row_to_adjustment(row)
    return result


def upsert_employee_adjustment(
    company_id: str,
    employee_id: str,
    year: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("id")
        .eq("employee_id", employee_id)
        .eq("year", year)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    payload = {
        **data,
        "company_id": company_id,
        "employee_id": employee_id,
        "year": year,
        "updated_at": now,
    }
    if rows:
        resp2 = (
            supabase.table("employee_leave_adjustments")
            .update(payload)
            .eq("employee_id", employee_id)
            .eq("year", year)
            .execute()
        )
    else:
        payload["created_at"] = now
        resp2 = supabase.table("employee_leave_adjustments").insert(payload).execute()
    if not resp2.data:
        raise RuntimeError("Upsert employee_leave_adjustments sans données")
    return resp2.data[0] if isinstance(resp2.data, list) else resp2.data


def list_company_adjustments(company_id: str, year: int) -> list[dict[str, Any]]:
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .eq("company_id", company_id)
        .eq("year", year)
        .execute()
    )
    return resp.data or []


def list_company_adjustments_avec_reference(company_id: str) -> list[dict[str, Any]]:
    """Reprises datées (bulletin importé, recalage) : celles dont l'écart
    dépend du calcul théorique à une date de référence."""
    resp = (
        supabase.table("employee_leave_adjustments")
        .select("*")
        .eq("company_id", company_id)
        .not_.is_("cp_opening_reference_date", "null")
        .execute()
    )
    return resp.data or []
