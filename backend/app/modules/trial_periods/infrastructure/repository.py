"""Persistance des périodes d'essai via Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from app.core.database import supabase
from app.modules.trial_periods.domain.constants import STATUS_EN_COURS
from app.modules.trial_periods.infrastructure.queries import (
    SELECT_TRIAL_WITH_EMPLOYEE,
    TABLE_TRIAL_PERIODS,
)


def _attach_employee_name(row: Dict[str, Any]) -> Dict[str, Any]:
    employee = row.pop("employee", None) or {}
    if employee:
        first = employee.get("first_name") or ""
        last = employee.get("last_name") or ""
        row["employee_name"] = f"{first} {last}".strip() or None
        row["hire_date"] = employee.get("hire_date")
        row["contract_type"] = employee.get("contract_type")
        row["statut"] = employee.get("statut")
    return row


class SupabaseTrialPeriodsRepository:
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        res = supabase.table(TABLE_TRIAL_PERIODS).insert(data).execute()
        if not res.data:
            raise RuntimeError("Insert trial_periods sans données retournées")
        return res.data[0]

    def get_by_id(self, trial_period_id: str) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .select(SELECT_TRIAL_WITH_EMPLOYEE)
            .eq("id", trial_period_id)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return _attach_employee_name(dict(rows[0])) if rows else None

    def get_active_for_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        res = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .select(SELECT_TRIAL_WITH_EMPLOYEE)
            .eq("employee_id", employee_id)
            .eq("status", STATUS_EN_COURS)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return _attach_employee_name(dict(rows[0])) if rows else None

    def update(self, trial_period_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload = {**data, "updated_at": datetime.now(timezone.utc).isoformat()}
        res = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .update(payload)
            .eq("id", trial_period_id)
            .execute()
        )
        if not res.data:
            raise RuntimeError(f"Période d'essai {trial_period_id} introuvable")
        return res.data[0]

    def list_for_company(
        self,
        company_id: str,
        statuses: Optional[Sequence[str]] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            supabase.table(TABLE_TRIAL_PERIODS)
            .select(SELECT_TRIAL_WITH_EMPLOYEE)
            .eq("company_id", company_id)
        )
        if statuses:
            query = query.in_("status", list(statuses))
        res = query.order("end_date").execute()
        return [_attach_employee_name(dict(row)) for row in (res.data or [])]


repository = SupabaseTrialPeriodsRepository()

__all__ = ["SupabaseTrialPeriodsRepository", "repository"]
