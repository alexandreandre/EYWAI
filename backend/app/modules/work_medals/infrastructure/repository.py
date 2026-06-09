"""Persistance Supabase — médailles du travail."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.database import supabase
from app.modules.work_medals.domain.interfaces import (
    AbstractWorkMedalCasesRepository,
    AbstractWorkMedalSettingsRepository,
)


class SupabaseWorkMedalSettingsRepository(AbstractWorkMedalSettingsRepository):
    def get_by_company(self, company_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("company_work_medal_settings")
            .select("*")
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id}
        payload.pop("created_at", None)
        if payload.get("id") is None:
            payload.pop("id", None)
        res = (
            supabase.table("company_work_medal_settings")
            .upsert(payload, on_conflict="company_id")
            .execute()
        )
        if not res.data:
            raise RuntimeError("Upsert company_work_medal_settings sans données")
        return res.data[0] if isinstance(res.data, list) else res.data


class SupabaseWorkMedalCasesRepository(AbstractWorkMedalCasesRepository):
    _SELECT = "*, employee:employees(first_name, last_name)"

    def list_by_company(
        self,
        company_id: str,
        *,
        status: str | None = None,
        medal_level: str | None = None,
    ) -> List[Dict[str, Any]]:
        q = (
            supabase.table("employee_work_medal_cases")
            .select(self._SELECT)
            .eq("company_id", company_id)
            .order("eligible_date")
        )
        if status:
            q = q.eq("status", status)
        if medal_level:
            q = q.eq("medal_level", medal_level)
        res = q.execute()
        return self._normalize_rows(res.data or [])

    def list_by_employee(self, employee_id: str) -> List[Dict[str, Any]]:
        res = (
            supabase.table("employee_work_medal_cases")
            .select(self._SELECT)
            .eq("employee_id", employee_id)
            .order("milestone_years")
            .execute()
        )
        return self._normalize_rows(res.data or [])

    def get_by_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employee_work_medal_cases")
            .select(self._SELECT)
            .eq("id", case_id)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return None
        rows = self._normalize_rows([r.data])
        return rows[0] if rows else None

    def get_by_employee_level(
        self, employee_id: str, medal_level: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("employee_work_medal_cases")
            .select("*")
            .eq("employee_id", employee_id)
            .eq("medal_level", medal_level)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def insert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        res = supabase.table("employee_work_medal_cases").insert(data).execute()
        if not res.data:
            raise RuntimeError("Insert employee_work_medal_cases sans données")
        return res.data[0]

    def update(self, case_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(data)
        payload.pop("created_at", None)
        res = (
            supabase.table("employee_work_medal_cases")
            .update(payload)
            .eq("id", case_id)
            .execute()
        )
        if not res.data:
            raise RuntimeError("Update employee_work_medal_cases sans données")
        return res.data[0]

    def count_by_status(self, company_id: str, statuses: List[str]) -> int:
        res = (
            supabase.table("employee_work_medal_cases")
            .select("id", count="exact")
            .eq("company_id", company_id)
            .in_("status", statuses)
            .execute()
        )
        return int(res.count or 0)

    @staticmethod
    def _normalize_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows:
            r = dict(row)
            emp = r.pop("employee", None)
            if isinstance(emp, list) and emp:
                emp = emp[0]
            if isinstance(emp, dict):
                r["employee_first_name"] = emp.get("first_name")
                r["employee_last_name"] = emp.get("last_name")
            out.append(r)
        return out


work_medal_settings_repository = SupabaseWorkMedalSettingsRepository()
work_medal_cases_repository = SupabaseWorkMedalCasesRepository()
