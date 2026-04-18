"""
Repository Supabase budget formation (training_budget).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.training_budget.domain.interfaces import AbstractTrainingBudgetRepository


def _breakdown_from_db(val: Any) -> Dict[str, Any]:
    if val is None:
        return {}
    if isinstance(val, dict):
        return dict(val)
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


class SupabaseTrainingBudgetRepository(AbstractTrainingBudgetRepository):
    """Implémentation Supabase."""

    def get_by_year(self, company_id: str, year: int) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("training_budget")
            .select("*")
            .eq("company_id", company_id)
            .eq("year", year)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            return None
        row = dict(r.data)
        row["service_breakdown"] = _breakdown_from_db(row.get("service_breakdown"))
        return row

    def get_all(self, company_id: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("training_budget")
            .select("*")
            .eq("company_id", company_id)
            .order("year", desc=True)
            .execute()
        )
        rows = [dict(x) for x in list(r.data or []) if r]
        for row in rows:
            row["service_breakdown"] = _breakdown_from_db(row.get("service_breakdown"))
        return rows

    def upsert(self, company_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        payload = {
            **data,
            "company_id": company_id,
            "updated_at": now,
        }
        ins = (
            supabase.table("training_budget")
            .upsert(payload, on_conflict="company_id,year")
            .execute()
        )
        if not ins.data:
            raise RuntimeError("Erreur lors de l'enregistrement du budget.")
        row = dict(ins.data[0])
        row["service_breakdown"] = _breakdown_from_db(row.get("service_breakdown"))
        return row


training_budget_repository: AbstractTrainingBudgetRepository = (
    SupabaseTrainingBudgetRepository()
)
