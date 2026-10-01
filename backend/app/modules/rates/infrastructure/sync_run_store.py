"""Persistance des lots de mise à jour de taux et de l'interrupteur mensuel."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from app.core.database import supabase


class MonthRunBusy(Exception):
    """Un run de ce mois est déjà en cours."""

    def __init__(self, sync_id: str) -> None:
        super().__init__("Une mise à jour du mois est déjà en cours.")
        self.sync_id = sync_id


class SyncRunStore(Protocol):
    def insert_run(self, row: Dict[str, Any]) -> None: ...

    def update_run(self, sync_id: str, fields: Dict[str, Any]) -> None: ...

    def get_run(self, sync_id: str) -> Optional[Dict[str, Any]]: ...

    def list_month(self, month_key: str) -> List[Dict[str, Any]]: ...

    def list_running(self) -> List[Dict[str, Any]]: ...

    def get_auto_enabled(self) -> bool: ...

    def set_auto_enabled(self, enabled: bool) -> None: ...


class MemorySyncRunStore:
    """Registre en mémoire, pour les tests."""

    def __init__(self) -> None:
        self._rows: Dict[str, Dict[str, Any]] = {}
        self.auto_enabled = True

    def insert_run(self, row: Dict[str, Any]) -> None:
        month = row.get("month_key")
        if month and row.get("status") == "running":
            for existing in self._rows.values():
                if existing.get("month_key") == month and existing.get("status") == "running":
                    raise MonthRunBusy(str(existing["id"]))
        self._rows[str(row["id"])] = dict(row)

    def update_run(self, sync_id: str, fields: Dict[str, Any]) -> None:
        current = self._rows.get(sync_id)
        if not current:
            return
        current.update(fields)

    def get_run(self, sync_id: str) -> Optional[Dict[str, Any]]:
        row = self._rows.get(sync_id)
        return dict(row) if row else None

    def list_month(self, month_key: str) -> List[Dict[str, Any]]:
        return [dict(row) for row in self._rows.values() if row.get("month_key") == month_key]

    def list_running(self) -> List[Dict[str, Any]]:
        return [dict(row) for row in self._rows.values() if row.get("status") == "running"]

    def get_auto_enabled(self) -> bool:
        return self.auto_enabled

    def set_auto_enabled(self, enabled: bool) -> None:
        self.auto_enabled = enabled


class DbSyncRunStore:
    def insert_run(self, row: Dict[str, Any]) -> None:
        try:
            supabase.table("rates_sync_runs").insert(row).execute()
        except Exception as exc:
            text = str(exc).lower()
            if "23505" in text or "duplicate" in text or "unique" in text:
                existing = ""
                month = row.get("month_key")
                if month:
                    found = (
                        supabase.table("rates_sync_runs")
                        .select("id")
                        .eq("month_key", month)
                        .eq("status", "running")
                        .limit(1)
                        .execute()
                    )
                    if found.data:
                        existing = str(found.data[0]["id"])
                raise MonthRunBusy(existing) from exc
            raise

    def update_run(self, sync_id: str, fields: Dict[str, Any]) -> None:
        supabase.table("rates_sync_runs").update(fields).eq("id", sync_id).execute()

    def get_run(self, sync_id: str) -> Optional[Dict[str, Any]]:
        result = (
            supabase.table("rates_sync_runs")
            .select("*")
            .eq("id", sync_id)
            .maybe_single()
            .execute()
        )
        return result.data if result and result.data else None

    def list_month(self, month_key: str) -> List[Dict[str, Any]]:
        result = (
            supabase.table("rates_sync_runs")
            .select("*")
            .eq("month_key", month_key)
            .order("started_at", desc=True)
            .execute()
        )
        return result.data or []

    def list_running(self) -> List[Dict[str, Any]]:
        result = (
            supabase.table("rates_sync_runs")
            .select("*")
            .eq("status", "running")
            .execute()
        )
        return result.data or []

    def get_auto_enabled(self) -> bool:
        result = (
            supabase.table("rates_monthly_settings")
            .select("auto_enabled")
            .eq("id", 1)
            .maybe_single()
            .execute()
        )
        if not result or not result.data:
            return True
        return bool(result.data.get("auto_enabled", True))

    def set_auto_enabled(self, enabled: bool) -> None:
        from datetime import datetime, timezone

        supabase.table("rates_monthly_settings").upsert(
            {
                "id": 1,
                "auto_enabled": enabled,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).execute()


_store: SyncRunStore = DbSyncRunStore()


def get_sync_run_store() -> SyncRunStore:
    return _store


def set_sync_run_store(store: SyncRunStore) -> None:
    global _store
    _store = store
