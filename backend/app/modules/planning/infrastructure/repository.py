"""
Repository Planning — accès Supabase (shifts, statuts, historique, référentiels).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import supabase

from app.modules.planning.domain.interfaces import AbstractPlanningRepository


class SupabasePlanningRepository(AbstractPlanningRepository):
    """Implémentation Supabase pour le module Planning."""

    # --- SHIFTS ---

    def create_shift(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("shifts").insert(data).execute()
        if not r or not r.data:
            raise RuntimeError("Échec de la création du shift.")
        return r.data[0]

    def get_shift_by_id(self, shift_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("shifts")
            .select("*")
            .eq("id", shift_id)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def update_shift(self, shift_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("shifts").update(data).eq("id", shift_id).execute()
        if not r or not r.data:
            raise RuntimeError("Échec de la mise à jour du shift.")
        return r.data[0]

    def delete_shift(self, shift_id: str) -> bool:
        r = supabase.table("shifts").delete().eq("id", shift_id).execute()
        return bool(r and r.data)

    def get_shifts_by_week(
        self, company_id: str, week_start: str, week_end: str
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("shifts")
            .select(
                "*, employees(id, first_name, last_name), "
                "shift_types(id, code, label, color)"
            )
            .eq("company_id", company_id)
            .gte("shift_date", week_start)
            .lte("shift_date", week_end)
            .execute()
        )
        return (r.data or []) if r else []

    def get_shifts_by_employee_week(
        self, employee_id: str, week_start: str, week_end: str
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("shifts")
            .select("*")
            .eq("employee_id", employee_id)
            .gte("shift_date", week_start)
            .lte("shift_date", week_end)
            .execute()
        )
        return (r.data or []) if r else []

    def lock_shift(self, shift_id: str) -> Dict[str, Any]:
        r = (
            supabase.table("shifts")
            .update({"is_locked": True})
            .eq("id", shift_id)
            .execute()
        )
        if not r or not r.data:
            raise RuntimeError("Échec du verrouillage du shift.")
        return r.data[0]

    def get_shifts_by_day(self, company_id: str, day_date: str) -> List[Dict[str, Any]]:
        r = (
            supabase.table("shifts")
            .select("*")
            .eq("company_id", company_id)
            .eq("shift_date", day_date)
            .execute()
        )
        return (r.data or []) if r else []

    # --- WEEK STATUS ---

    def get_week_status(
        self, company_id: str, week_start: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("planning_week_status")
            .select("*")
            .eq("company_id", company_id)
            .eq("week_start", week_start)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def upsert_week_status(
        self, company_id: str, week_start: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id, "week_start": week_start}
        res = (
            supabase.table("planning_week_status")
            .upsert(payload, on_conflict="company_id,week_start")
            .execute()
        )
        if not res or not res.data:
            raise RuntimeError("Upsert planning_week_status sans données retournées.")
        row = res.data[0] if isinstance(res.data, list) else res.data
        return row

    def lock_week(
        self, company_id: str, week_start: str, locked_by: str
    ) -> Dict[str, Any]:
        r = (
            supabase.table("planning_week_status")
            .update(
                {
                    "status": "locked",
                    "locked_at": datetime.now(timezone.utc).isoformat(),
                    "locked_by": locked_by,
                }
            )
            .eq("company_id", company_id)
            .eq("week_start", week_start)
            .execute()
        )
        if not r or not r.data:
            raise RuntimeError("Échec du verrouillage de la semaine.")
        return r.data[0]

    def set_payroll_transmitted(
        self, company_id: str, week_start: str
    ) -> Dict[str, Any]:
        r = (
            supabase.table("planning_week_status")
            .update(
                {
                    "payroll_transmitted": True,
                    "payroll_transmitted_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("company_id", company_id)
            .eq("week_start", week_start)
            .execute()
        )
        if not r or not r.data:
            raise RuntimeError("Échec de la mise à jour transmission paie.")
        return r.data[0]

    # --- DAY STATUS ---

    def get_day_status(
        self, company_id: str, day_date: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("planning_day_status")
            .select("*")
            .eq("company_id", company_id)
            .eq("day_date", day_date)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def upsert_day_status(
        self, company_id: str, day_date: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id, "day_date": day_date}
        res = (
            supabase.table("planning_day_status")
            .upsert(payload, on_conflict="company_id,day_date")
            .execute()
        )
        if not res or not res.data:
            raise RuntimeError("Upsert planning_day_status sans données retournées.")
        row = res.data[0] if isinstance(res.data, list) else res.data
        return row

    # --- LOCK HISTORY ---

    def create_lock_history(self, data: Dict[str, Any]) -> Dict[str, Any]:
        r = supabase.table("planning_lock_history").insert(data).execute()
        if not r or not r.data:
            raise RuntimeError("Échec de la création de l'historique de verrouillage.")
        return r.data[0]

    def get_lock_history(self, company_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        r = (
            supabase.table("planning_lock_history")
            .select("*")
            .eq("company_id", company_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return (r.data or []) if r else []

    # --- SHIFT TYPES ---

    def get_shift_types_by_cc(
        self, collective_agreement_id: str
    ) -> List[Dict[str, Any]]:
        r = (
            supabase.table("shift_types")
            .select("*")
            .eq("collective_agreement_id", collective_agreement_id)
            .order("code")
            .execute()
        )
        return (r.data or []) if r else []

    def get_all_active_shift_types(self) -> List[Dict[str, Any]]:
        r = (
            supabase.table("shift_types")
            .select("*")
            .eq("is_active", True)
            .order("code")
            .execute()
        )
        return (r.data or []) if r else []

    # --- COLLECTIVE AGREEMENTS ---

    def get_all_collective_agreements(self) -> List[Dict[str, Any]]:
        r = (
            supabase.table("collective_agreements")
            .select("*")
            .order("code")
            .execute()
        )
        return (r.data or []) if r else []

    def get_cc_by_id(self, cc_id: str) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("collective_agreements")
            .select("*")
            .eq("id", cc_id)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    # --- COMPANY SETTINGS ---

    def get_company_planning_settings(
        self, company_id: str
    ) -> Optional[Dict[str, Any]]:
        r = (
            supabase.table("company_planning_settings")
            .select("*")
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return r.data if r else None

    def update_company_planning_settings(
        self, company_id: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        payload = {**data, "company_id": company_id}
        res = (
            supabase.table("company_planning_settings")
            .upsert(payload, on_conflict="company_id")
            .execute()
        )
        if not res or not res.data:
            raise RuntimeError("Upsert company_planning_settings sans données retournées.")
        row = res.data[0] if isinstance(res.data, list) else res.data
        return row


planning_repository = SupabasePlanningRepository()
