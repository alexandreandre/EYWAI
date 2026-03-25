"""
Repository employee_schedules : implémentation Supabase du port IScheduleRepository.

Tout accès DB à la table employee_schedules. Comportement identique à l'ancien router.
"""

import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import supabase
from app.modules.schedules.domain.interfaces import IScheduleRepository
from app.modules.schedules.infrastructure.mappers import (
    row_to_planned_calendar,
    row_to_actual_hours,
)


class ScheduleRepository(IScheduleRepository):
    """Implémentation Supabase pour employee_schedules."""

    def get_planned_calendar(
        self, employee_id: str, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employee_schedules")
            .select("planned_calendar")
            .match({"employee_id": employee_id, "year": year, "month": month})
            .maybe_single()
            .execute()
        )
        return row_to_planned_calendar(response.data if response else None)

    def get_actual_hours(
        self, employee_id: str, year: int, month: int
    ) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employee_schedules")
            .select("actual_hours")
            .match({"employee_id": employee_id, "year": year, "month": month})
            .maybe_single()
            .execute()
        )
        return row_to_actual_hours(response.data if response else None)

    def upsert_schedule(
        self,
        employee_id: str,
        company_id: str,
        year: int,
        month: int,
        *,
        planned_calendar: Optional[Dict[str, Any]] = None,
        actual_hours: Optional[Dict[str, Any]] = None,
        payroll_events: Optional[Dict[str, Any]] = None,
        cumuls: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": year,
            "month": month,
        }
        if planned_calendar is not None:
            payload["planned_calendar"] = planned_calendar
        if actual_hours is not None:
            payload["actual_hours"] = actual_hours
        if payroll_events is not None:
            payload["payroll_events"] = payroll_events
        if cumuls is not None:
            payload["cumuls"] = cumuls
        try:
            supabase.table("employee_schedules").upsert(
                payload, on_conflict="employee_id,year,month"
            ).execute()
        except Exception as e:
            print(f"❌ Erreur lors de l'upsert Supabase: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            supabase.table("employee_schedules").upsert(
                payload, on_conflict="employee_id,year,month"
            ).execute()

    def get_schedules_for_months(
        self,
        employee_id: str,
        year_months: List[Tuple[int, int]],
    ) -> List[Dict[str, Any]]:
        if not year_months:
            return []
        years = list({y for y, _ in year_months})
        months = list({m for _, m in year_months})
        response = (
            supabase.table("employee_schedules")
            .select("year, month, planned_calendar, actual_hours")
            .eq("employee_id", employee_id)
            .in_("year", years)
            .in_("month", months)
            .execute()
        )
        return response.data if response and response.data else []

    def get_latest_cumuls_row(self, employee_id: str) -> Optional[Dict[str, Any]]:
        response = (
            supabase.table("employee_schedules")
            .select("cumuls")
            .eq("employee_id", employee_id)
            .not_.is_("cumuls", "null")
            .order("year", desc=True)
            .order("month", desc=True)
            .limit(1)
            .maybe_single()
            .execute()
        )
        return response.data if response and response.data else None

    def update_payroll_events(
        self, employee_id: str, year: int, month: int, payroll_events: Dict[str, Any]
    ) -> None:
        supabase.table("employee_schedules").update(
            {"payroll_events": payroll_events}
        ).match({"employee_id": employee_id, "year": year, "month": month}).execute()

    def exists_schedule(self, employee_id: str, year: int, month: int) -> bool:
        response = (
            supabase.table("employee_schedules")
            .select("id")
            .match({"employee_id": employee_id, "year": year, "month": month})
            .maybe_single()
            .execute()
        )
        return bool(response and response.data)

    def insert_schedule(
        self,
        employee_id: str,
        company_id: str,
        year: int,
        month: int,
        planned_calendar: Dict[str, Any],
        actual_hours: Optional[Dict[str, Any]] = None,
        payroll_events: Optional[Dict[str, Any]] = None,
        cumuls: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "employee_id": employee_id,
            "company_id": company_id,
            "year": year,
            "month": month,
            "planned_calendar": planned_calendar,
            "actual_hours": actual_hours or {},
            "payroll_events": payroll_events or {},
            "cumuls": cumuls or {},
        }
        supabase.table("employee_schedules").insert(payload).execute()

    def update_planned_calendar_only(
        self, employee_id: str, year: int, month: int, planned_calendar: Dict[str, Any]
    ) -> None:
        supabase.table("employee_schedules").update(
            {"planned_calendar": planned_calendar}
        ).match({"employee_id": employee_id, "year": year, "month": month}).execute()


# Instance pour l'application
schedule_repository = ScheduleRepository()
