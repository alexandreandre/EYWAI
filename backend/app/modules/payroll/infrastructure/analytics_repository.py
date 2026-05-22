"""Lecture Supabase pour Analytics Paie."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional, Set

from app.core.database import supabase


def _to_float(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


class PayrollAnalyticsRepository:
    def fetch_active_employees(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("employees")
            .select(
                "id, team_id, service_id, contract_type, employment_status, "
                "first_name, last_name"
            )
            .eq("company_id", company_id)
            .in_("employment_status", ["actif", "active"])
            .execute()
        )
        return [dict(row) for row in (r.data or []) if isinstance(row, dict)]

    def fetch_payslips_for_company(
        self, company_id: str, *, year: Optional[int] = None, month: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("payslips")
            .select(
                "id, employee_id, year, month, status, payslip_data, company_id, validated_at"
            )
            .eq("company_id", company_id)
        )
        if year is not None:
            q = q.eq("year", year)
        if month is not None:
            q = q.eq("month", month)
        r = q.execute()
        return [dict(row) for row in (r.data or []) if isinstance(row, dict)]

    def fetch_teams(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("teams")
            .select("id, name")
            .eq("company_id", company_id)
            .eq("status", "active")
            .order("name")
            .execute()
        )
        return [dict(row) for row in (r.data or []) if isinstance(row, dict)]

    def fetch_services(self, company_id: str) -> Dict[str, str]:
        r = (
            supabase.table("company_services")
            .select("id, name")
            .eq("company_id", company_id)
            .execute()
        )
        out: Dict[str, str] = {}
        for row in r.data or []:
            if isinstance(row, dict) and row.get("id"):
                out[str(row["id"])] = str(row.get("name") or "Service")
        return out

    def count_pending_expenses(self, company_id: str) -> int:
        r = (
            supabase.table("expense_reports")
            .select("id", count="exact")
            .eq("company_id", company_id)
            .eq("status", "pending")
            .execute()
        )
        return int(r.count or 0) if r else 0

    def count_pending_absences(self, company_id: str) -> int:
        r = (
            supabase.table("absence_requests")
            .select("id", count="exact")
            .eq("company_id", company_id)
            .eq("status", "pending")
            .execute()
        )
        return int(r.count or 0) if r else 0

    def count_monthly_inputs(
        self, employee_ids: Set[str], year: int, month: int
    ) -> int:
        if not employee_ids:
            return 0
        r = (
            supabase.table("monthly_inputs")
            .select("employee_id")
            .eq("year", year)
            .eq("month", month)
            .execute()
        )
        n = 0
        for row in r.data or []:
            if isinstance(row, dict) and str(row.get("employee_id") or "") in employee_ids:
                n += 1
        return n

    def count_active_advances(self, employee_ids: Set[str]) -> int:
        if not employee_ids:
            return 0
        r = (
            supabase.table("salary_advances")
            .select("employee_id, remaining_amount, status")
            .in_("status", ["approved", "paid"])
            .execute()
        )
        n = 0
        for row in r.data or []:
            if not isinstance(row, dict):
                continue
            if str(row.get("employee_id") or "") not in employee_ids:
                continue
            if _to_float(row.get("remaining_amount")) > 0:
                n += 1
        return n

    def fetch_payroll_runs(self, company_id: str, year: int) -> List[Dict[str, Any]]:
        try:
            r = (
                supabase.table("payroll_runs")
                .select("period_start, status, closed_at, closed_by")
                .eq("company_id", company_id)
                .execute()
            )
        except Exception:
            return []
        rows = (r.data or []) if r else []
        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            ps = str(row.get("period_start") or "")[:10]
            try:
                d = date.fromisoformat(ps)
            except ValueError:
                continue
            if d.year != year:
                continue
            out.append(
                {
                    "year": d.year,
                    "month": d.month,
                    "status": str(row.get("status") or "open"),
                    "closed_at": row.get("closed_at"),
                    "closed_by": row.get("closed_by"),
                }
            )
        return out

    def is_period_closed(self, company_id: str, year: int, month: int) -> bool:
        for row in self.fetch_payroll_runs(company_id, year):
            if row.get("month") == month and str(row.get("status")) == "closed":
                return True
        return False


payroll_analytics_repository = PayrollAnalyticsRepository()
