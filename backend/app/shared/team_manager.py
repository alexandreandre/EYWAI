"""Résolution manager d'équipe — source canonique (teams.manager_employee_id)."""

from __future__ import annotations

from typing import List, Optional

from app.core.database import supabase


def get_team_manager_employee_id(employee_id: str) -> Optional[str]:
    """Retourne l'employee_id du manager d'équipe si défini."""
    emp = (
        supabase.table("employees")
        .select("team_id")
        .eq("id", employee_id)
        .maybe_single()
        .execute()
    )
    if not emp or not emp.data:
        return None
    team_id = emp.data.get("team_id")
    if not team_id:
        return None
    team = (
        supabase.table("teams")
        .select("manager_employee_id")
        .eq("id", str(team_id))
        .maybe_single()
        .execute()
    )
    if not team or not team.data:
        return None
    mid = team.data.get("manager_employee_id")
    return str(mid) if mid else None


def get_employee_ids_managed_by_manager(
    manager_employee_id: str, company_id: str
) -> List[str]:
    """IDs des employés dont l'équipe a ce manager (teams actives)."""
    teams_r = (
        supabase.table("teams")
        .select("id")
        .eq("company_id", company_id)
        .eq("status", "active")
        .eq("manager_employee_id", manager_employee_id)
        .execute()
    )
    team_ids = [str(t["id"]) for t in (teams_r.data or [])]
    if not team_ids:
        return []
    out: List[str] = []
    for tid in team_ids:
        emps = (
            supabase.table("employees")
            .select("id")
            .eq("team_id", tid)
            .execute()
        )
        for row in emps.data or []:
            eid = row.get("id")
            if eid:
                out.append(str(eid))
    return out
