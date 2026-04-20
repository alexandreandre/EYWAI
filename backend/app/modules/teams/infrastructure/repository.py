"""Accès Supabase — module Équipes."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.core.database import supabase


def _to_float(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _payslip_period_bounds(year: int, month: int) -> tuple[date, date]:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _month_overlaps_period(year: int, month: int, p_start: date, p_end: date) -> bool:
    m_start, m_end = _payslip_period_bounds(year, month)
    return not (m_end < p_start or m_start > p_end)


def _parse_iso_date(s: str) -> date:
    return datetime.fromisoformat(s[:10]).date()


class SupabaseTeamsRepository:
    """Repository Supabase pour teams + requêtes analytiques."""

    _MANAGER_EMBED = (
        "*, employees!teams_manager_employee_id_fkey(id, first_name, last_name)"
    )

    def create_team(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("teams").insert(data).execute()
        if not r.data:
            raise RuntimeError("Échec création équipe.")
        return dict(r.data[0])

    def get_team_by_id(self, team_id: str) -> Optional[Dict[str, Any]]:
        try:
            r = (
                supabase.table("teams")
                .select(self._MANAGER_EMBED)
                .eq("id", team_id)
                .maybe_single()
                .execute()
            )
        except Exception:
            r = (
                supabase.table("teams")
                .select("*")
                .eq("id", team_id)
                .maybe_single()
                .execute()
            )
        row = r.data if r else None
        if row is None or not isinstance(row, dict):
            return None
        return dict(row)

    def count_teams_by_company_and_status(
        self, company_id: str, status: str
    ) -> int:
        r = (
            supabase.table("teams")
            .select("id", count="exact")
            .eq("company_id", company_id)
            .eq("status", status)
            .execute()
        )
        return int(r.count or 0) if r else 0

    def get_teams_by_company(
        self, company_id: str, include_archived: bool = False
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("teams")
            .select(self._MANAGER_EMBED)
            .eq("company_id", company_id)
        )
        if not include_archived:
            q = q.eq("status", "active")
        try:
            r = q.order("name", desc=False).execute()
        except Exception:
            q2 = supabase.table("teams").select("*").eq("company_id", company_id)
            if not include_archived:
                q2 = q2.eq("status", "active")
            r = q2.order("name", desc=False).execute()
        rows = (r.data or []) if r else []
        return [dict(row) for row in rows if isinstance(row, dict)]

    def update_team(self, team_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("teams").update(data).eq("id", team_id).execute()
        if not r.data:
            raise RuntimeError("Échec mise à jour.")
        return dict(r.data[0])

    def archive_team(self, team_id: str) -> Dict[str, Any]:
        return self.update_team(team_id, {"status": "archived"})

    def reactivate_team(self, team_id: str) -> Dict[str, Any]:
        return self.update_team(team_id, {"status": "active"})

    def delete_team(self, team_id: str) -> bool:
        r = supabase.table("teams").delete().eq("id", team_id).execute()
        rows = (r.data or []) if r else []
        return len(rows) > 0

    def check_name_exists(
        self,
        company_id: str,
        name: str,
        exclude_team_id: Optional[str] = None,
    ) -> bool:
        q = (
            supabase.table("teams")
            .select("id")
            .eq("company_id", company_id)
            .ilike("name", name.strip())
        )
        if exclude_team_id:
            q = q.neq("id", exclude_team_id)
        r = q.limit(1).execute()
        rows = (r.data or []) if r else []
        return len(rows) > 0

    def get_employee_count(self, team_id: str) -> int:
        r = (
            supabase.table("employees")
            .select("id", count="exact")
            .eq("team_id", team_id)
            .execute()
        )
        return int(r.count or 0) if r else 0

    def get_employees_by_team(self, team_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, first_name, last_name, job_title")
            .eq("team_id", team_id)
            .order("last_name", desc=False)
            .execute()
        )
        return (r.data or []) if r else []

    def assign_employee_team(
        self, employee_id: str, team_id: Optional[str]
    ) -> Dict[str, Any]:
        upd = {"team_id": team_id}
        r = (
            supabase.table("employees")
            .update(upd)
            .eq("id", employee_id)
            .execute()
        )
        if not r.data:
            raise RuntimeError("Échec mise à jour.")
        return dict(r.data[0])

    def unassign_team_employees(self, team_id: str) -> None:
        supabase.table("employees").update({"team_id": None}).eq(
            "team_id", team_id
        ).execute()

    def get_employee_row(self, employee_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, company_id, team_id, employment_status")
            .eq("id", employee_id)
            .maybe_single()
            .execute()
        )
        row = r.data if r else None
        if row is None or not isinstance(row, dict):
            return None
        return dict(row)

    def get_employee_in_company(
        self, employee_id: str, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, company_id, team_id, employment_status")
            .eq("id", employee_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        row = r.data if r else None
        if row is None or not isinstance(row, dict):
            return None
        return dict(row)

    def get_employees_with_team(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select("id, team_id, duree_hebdomadaire, employment_status")
            .eq("company_id", company_id)
            .in_("employment_status", ["actif", "active"])
            .execute()
        )
        return (r.data or []) if r else []

    def get_payslips_for_period(
        self, company_id: str, period_start: str, period_end: str
    ) -> List[Dict[str, Any]]:
        p_start = _parse_iso_date(period_start)
        p_end = _parse_iso_date(period_end)
        r = (
            supabase.table("payslips")
            .select("employee_id, year, month, payslip_data, status, company_id")
            .eq("company_id", company_id)
            .eq("status", "valide")
            .execute()
        )
        rows = (r.data or []) if r else []
        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            y = row.get("year")
            m = row.get("month")
            if y is None or m is None:
                continue
            try:
                yi, mi = int(y), int(m)
            except (TypeError, ValueError):
                continue
            if not _month_overlaps_period(yi, mi, p_start, p_end):
                continue
            pd = row.get("payslip_data") or {}
            if not isinstance(pd, dict):
                pd = {}
            pied = pd.get("pied_de_page") or {}
            if not isinstance(pied, dict):
                pied = {}
            out.append(
                {
                    "employee_id": str(row.get("employee_id") or ""),
                    "salaire_brut": _to_float(pd.get("salaire_brut")),
                    "cout_total_employeur": _to_float(
                        pied.get("cout_total_employeur")
                    ),
                    "year": yi,
                    "month": mi,
                }
            )
        return out

    def get_expenses_for_period(
        self, company_id: str, period_start: str, period_end: str
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("expense_reports")
            .select("employee_id, amount, status, created_at, company_id")
            .eq("company_id", company_id)
            .eq("status", "validated")
            .gte("created_at", f"{period_start}T00:00:00")
            .lte("created_at", f"{period_end}T23:59:59.999999")
            .execute()
        )
        return (r.data or []) if r else []

    def get_absences_for_period(
        self, company_id: str, period_start: str, period_end: str
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("absence_requests")
            .select("employee_id, selected_days, type, status, company_id")
            .eq("company_id", company_id)
            .eq("status", "validated")
            .execute()
        )
        rows = (r.data or []) if r else []
        p_start = _parse_iso_date(period_start)
        p_end = _parse_iso_date(period_end)
        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            days = row.get("selected_days") or []
            if not isinstance(days, list):
                continue
            filtered_days: List[str] = []
            for d in days:
                if not isinstance(d, str):
                    continue
                try:
                    dd = datetime.fromisoformat(d.replace("Z", "+00:00")).date()
                except (ValueError, TypeError):
                    continue
                if p_start <= dd <= p_end:
                    filtered_days.append(d)
            if filtered_days:
                out.append(
                    {
                        "employee_id": str(row.get("employee_id") or ""),
                        "selected_days": filtered_days,
                        "type": row.get("type"),
                    }
                )
        return out


teams_repository = SupabaseTeamsRepository()
