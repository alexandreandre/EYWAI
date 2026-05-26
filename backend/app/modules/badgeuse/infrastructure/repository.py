from __future__ import annotations

from datetime import datetime, date
from typing import Any, List, Dict, Optional, Set

from app.core.database import supabase
from app.modules.badgeuse.infrastructure.db_errors import execute_supabase
from app.modules.badgeuse.domain.time_tracking import (
    TimeEntry,
    TimeEntryType,
    TimeEntrySource,
)


class TimeEntryRepository:
    """Accès Supabase à la table employee_time_entries."""

    table_name = "employee_time_entries"

    def _row_to_entry(self, row: dict[str, Any]) -> TimeEntry:
        return TimeEntry(
            id=str(row.get("id")) if row.get("id") else None,
            employee_id=str(row["employee_id"]),
            company_id=str(row["company_id"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=TimeEntryType(row["event_type"]),
            source=TimeEntrySource(row.get("source") or TimeEntrySource.EMPLOYE),
        )

    def get_entries_for_employee_between(
        self,
        employee_id: str,
        company_id: str,
        start: datetime,
        end: datetime,
    ) -> List[TimeEntry]:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("*")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .gte("timestamp", start.isoformat())
            .lte("timestamp", end.isoformat())
            .order("timestamp", desc=False)
            .execute()
        )
        rows = result.data or []
        return [self._row_to_entry(r) for r in rows]

    def get_entries_for_employee_on_day(
        self,
        employee_id: str,
        company_id: str,
        day: date,
    ) -> List[TimeEntry]:
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        return self.get_entries_for_employee_between(
            employee_id, company_id, start, end
        )

    def insert_entry(
        self,
        *,
        employee_id: str,
        company_id: str,
        timestamp: datetime,
        event_type: TimeEntryType,
        source: TimeEntrySource,
        created_by: Optional[str],
    ) -> TimeEntry:
        payload: Dict[str, Any] = {
            "employee_id": employee_id,
            "company_id": company_id,
            "timestamp": timestamp.isoformat(),
            "event_type": event_type.value,
            "source": source.value,
        }
        if created_by:
            payload["created_by"] = created_by
        result = execute_supabase(
            lambda: supabase.table(self.table_name).insert(payload).execute()
        )
        row = (result.data or [None])[0]
        if not row:
            raise RuntimeError("Erreur lors de la création du pointage")
        return self._row_to_entry(row)

    def update_entry(
        self,
        entry_id: str,
        *,
        timestamp: Optional[datetime] = None,
        event_type: Optional[TimeEntryType] = None,
        updated_by: Optional[str] = None,
    ) -> TimeEntry:
        payload: Dict[str, Any] = {}
        if timestamp is not None:
            payload["timestamp"] = timestamp.isoformat()
        if event_type is not None:
            payload["event_type"] = event_type.value
        if updated_by is not None:
            payload["updated_by"] = updated_by
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .update(payload)
            .eq("id", entry_id)
            .execute()
        )
        row = (result.data or [None])[0]
        if not row:
            raise RuntimeError("Pointage non trouvé pour mise à jour")
        return self._row_to_entry(row)

    def delete_entry(self, entry_id: str) -> None:
        execute_supabase(
            lambda: supabase.table(self.table_name).delete().eq("id", entry_id).execute()
        )

    def get_anomalies_over_period(
        self,
        company_id: str,
        start: datetime,
        end: datetime,
    ) -> List[dict[str, Any]]:
        """
        Récupère les événements bruts pour les jours potentiellement en anomalie.
        Le filtrage précis par type d'anomalie est fait en mémoire via les règles de domaine.
        """
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("*")
            .eq("company_id", company_id)
            .gte("timestamp", start.isoformat())
            .lte("timestamp", end.isoformat())
            .order("employee_id", desc=False)
            .order("timestamp", desc=False)
            .execute()
        )
        return result.data or []

    def get_entries_for_company_between(
        self,
        company_id: str,
        start: datetime,
        end: datetime,
        employee_ids: Optional[List[str]] = None,
    ) -> List[dict[str, Any]]:
        """
        Événements pour une entreprise sur une période, éventuellement filtrés par employés.
        Utilisé pour les synthèses et exports RH.
        """
        query = (
            supabase.table(self.table_name)
            .select("*")
            .eq("company_id", company_id)
            .gte("timestamp", start.isoformat())
            .lte("timestamp", end.isoformat())
        )
        if employee_ids:
            query = query.in_("employee_id", employee_ids)
        result = execute_supabase(
            lambda: query.order("employee_id").order("timestamp").execute()
        )
        return result.data or []


time_entry_repository = TimeEntryRepository()


class TimeEntryValidationRepository:
    """
    Accès Supabase aux validations de journées de badgeuse.
    Table attendue : employee_time_entries_validations
    avec au minimum : id, employee_id, company_id, day (date), validated_by, validated_at.
    """

    table_name = "employee_time_entries_validations"

    def set_day_validated(
        self,
        *,
        employee_id: str,
        company_id: str,
        day: date,
        validated_by: str,
    ) -> None:
        payload: Dict[str, Any] = {
            "employee_id": employee_id,
            "company_id": company_id,
            "day": day.isoformat(),
            "validated_by": validated_by,
            "validated_at": datetime.utcnow().isoformat(),
        }

        # On tente de trouver une validation existante pour cette journée
        existing = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("id")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .eq("day", day.isoformat())
            .execute()
        )
        rows = existing.data or []
        if rows:
            execute_supabase(
                lambda: supabase.table(self.table_name)
                .update(payload)
                .eq("id", rows[0]["id"])
                .execute()
            )
        else:
            execute_supabase(
                lambda: supabase.table(self.table_name).insert(payload).execute()
            )

    def get_validated_days_for_employee_between(
        self,
        *,
        employee_id: str,
        company_id: str,
        start: date,
        end: date,
    ) -> Set[date]:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("day")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .gte("day", start.isoformat())
            .lte("day", end.isoformat())
            .execute()
        )
        rows = result.data or []
        return {date.fromisoformat(r["day"]) for r in rows if r.get("day")}

    def is_day_validated(
        self,
        *,
        employee_id: str,
        company_id: str,
        day: date,
    ) -> bool:
        result = execute_supabase(
            lambda: supabase.table(self.table_name)
            .select("id")
            .eq("employee_id", employee_id)
            .eq("company_id", company_id)
            .eq("day", day.isoformat())
            .limit(1)
            .execute()
        )
        return bool(result.data)


time_entry_validation_repository = TimeEntryValidationRepository()
