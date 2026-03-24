"""
Providers infrastructure : heures réalisées employé (pour calcul prime selon_heures).

Source : table employee_schedules, champ actual_hours.calendrier_reel.
"""
from __future__ import annotations

from app.core.database import supabase
from app.modules.bonus_types.domain.interfaces import IEmployeeHoursProvider
from app.modules.bonus_types.infrastructure.queries import TABLE_EMPLOYEE_SCHEDULES


class SupabaseEmployeeHoursProvider:
    """Lit les heures réalisées via Supabase (employee_schedules.actual_hours)."""

    def get_total_actual_hours(
        self,
        employee_id: str,
        year: int,
        month: int,
    ) -> float:
        """Somme des heures_faites sur le mois (calendrier_reel)."""
        response = (
            supabase.table(TABLE_EMPLOYEE_SCHEDULES)
            .select("actual_hours")
            .eq("employee_id", employee_id)
            .eq("year", year)
            .eq("month", month)
            .maybe_single()
            .execute()
        )
        total_hours = 0.0
        if response.data and response.data.get("actual_hours"):
            calendrier_reel = response.data["actual_hours"].get("calendrier_reel", [])
            for day in calendrier_reel:
                h = day.get("heures_faites")
                if h is not None:
                    total_hours += float(h)
        return total_hours
