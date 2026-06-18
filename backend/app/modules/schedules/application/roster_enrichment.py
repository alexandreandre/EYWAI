"""Enrichissement du roster pour l'import de pointages (matricule GTA)."""

from __future__ import annotations

from app.core.database import supabase
from app.modules.schedules.schemas.ai import RosterEmployee


def enrich_roster_time_tracking_ids(
    roster: list[RosterEmployee],
    company_id: str | None,
) -> list[RosterEmployee]:
    if not company_id or not roster:
        return roster
    ids = [e.id for e in roster]
    try:
        resp = (
            supabase.table("employees")
            .select("id, time_tracking_id")
            .in_("id", ids)
            .execute()
        )
    except Exception:
        return roster
    by_id = {
        row["id"]: (row.get("time_tracking_id") or "").strip() or None
        for row in (resp.data or [])
    }
    return [
        RosterEmployee(
            id=e.id,
            first_name=e.first_name,
            last_name=e.last_name,
            time_tracking_id=by_id.get(e.id) or e.time_tracking_id,
        )
        for e in roster
    ]


__all__ = ["enrich_roster_time_tracking_ids"]
