"""Queries et commands routage HS manuel."""

from __future__ import annotations

from typing import Any

from app.core.database import supabase
from app.modules.modulation.application.reference_resolution import (
    resolve_effective_weekly_hours_map,
)
from app.modules.modulation.domain.hour_account_rules import sum_hs_from_payroll_events
from app.modules.modulation.infrastructure import overtime_routing_repository as otr_repo
from app.modules.modulation.infrastructure import repository as mod_repo
from app.shared.infrastructure.payroll_analyzer import analyser_horaires_du_mois


def _employee_hs_for_month(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    duree_hebdo: float,
) -> float:
    dates = []
    for delta in (-1, 0, 1):
        m = month + delta
        y = year
        if m < 1:
            m, y = 12, year - 1
        elif m > 12:
            m, y = 1, year + 1
        dates.append((y, m))

    rows = (
        supabase.table("employee_schedules")
        .select("year, month, planned_calendar, actual_hours")
        .eq("employee_id", employee_id)
        .execute()
    ).data or []

    planned_all: list[dict[str, Any]] = []
    actual_all: list[dict[str, Any]] = []
    ym_set = set(dates)
    for row in rows:
        y, m = int(row["year"]), int(row["month"])
        if (y, m) not in ym_set:
            continue
        planned_raw = row.get("planned_calendar") or {}
        actual_raw = row.get("actual_hours") or {}
        for entry in (planned_raw.get("calendrier_prevu") or []):
            e = dict(entry)
            e.update({"annee": y, "mois": m})
            planned_all.append(e)
        for entry in (actual_raw.get("calendrier_reel") or []):
            e = dict(entry)
            e.update({"annee": y, "mois": m})
            actual_all.append(e)

    weekly_map = resolve_effective_weekly_hours_map(company_id, year, duree_hebdo)
    events = analyser_horaires_du_mois(
        planned_all,
        actual_all,
        duree_hebdo,
        year,
        month,
        "",
        modulation_weekly_hours=weekly_map,
    )
    return sum_hs_from_payroll_events(events)


def list_overtime_routing(
    company_id: str, year: int, month: int
) -> list[dict[str, Any]]:
    settings = mod_repo.get_modulation_settings(company_id)
    if settings.hs_routing_policy != "manual":
        return []

    emp_res = (
        supabase.table("employees")
        .select("id, first_name, last_name, duree_hebdomadaire")
        .eq("company_id", company_id)
        .eq("employment_status", "actif")
        .execute()
    )
    decisions = {
        str(d["employee_id"]): d
        for d in otr_repo.list_for_period(company_id, year, month)
    }
    out = []
    for emp in emp_res.data or []:
        eid = str(emp["id"])
        duree = float(emp.get("duree_hebdomadaire") or 35)
        total_hs = _employee_hs_for_month(company_id, eid, year, month, duree)
        if total_hs <= 0:
            continue
        decision = decisions.get(eid)
        out.append(
            {
                "employee_id": eid,
                "employee_name": f"{emp.get('first_name', '')} {emp.get('last_name', '')}".strip(),
                "total_hs_hours": total_hs,
                "hours_to_pay": float(decision.get("hours_to_pay") or 0) if decision else 0,
                "hours_to_account": float(decision.get("hours_to_account") or 0) if decision else 0,
                "status": str(decision.get("status") or "pending") if decision else "pending",
                "note": decision.get("note") if decision else None,
            }
        )
    return out


def upsert_overtime_routing_decision(
    company_id: str,
    employee_id: str,
    year: int,
    month: int,
    hours_to_pay: float,
    hours_to_account: float,
    *,
    decided_by: str | None = None,
    note: str | None = None,
    validate: bool = False,
) -> dict[str, Any]:
    emp = (
        supabase.table("employees")
        .select("duree_hebdomadaire")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .limit(1)
        .execute()
    )
    if not emp.data:
        raise ValueError("Salarié introuvable.")
    duree = float(emp.data[0].get("duree_hebdomadaire") or 35)
    total_hs = _employee_hs_for_month(company_id, employee_id, year, month, duree)
    to_pay = round(max(0.0, float(hours_to_pay)), 2)
    to_account = round(max(0.0, float(hours_to_account)), 2)
    if round(to_pay + to_account, 2) != round(total_hs, 2):
        raise ValueError(
            f"La somme payer + compteur ({to_pay + to_account} h) doit égaler le total HS ({total_hs} h)."
        )
    return otr_repo.upsert_decision(
        {
            "company_id": company_id,
            "employee_id": employee_id,
            "year": year,
            "month": month,
            "total_hs_hours": total_hs,
            "hours_to_pay": to_pay,
            "hours_to_account": to_account,
            "status": "validated" if validate else "pending",
            "decided_by": decided_by,
            "note": note,
        }
    )
