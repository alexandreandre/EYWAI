"""Enrichissement du roster pour l'import de pointages (matricule GTA, nom d'usage)."""

from __future__ import annotations

from app.core.database import supabase
from app.modules.schedules.schemas.ai import RosterEmployee


def enrich_roster_time_tracking_ids(
    roster: list[RosterEmployee],
    company_id: str | None,
) -> list[RosterEmployee]:
    """Complète le roster envoyé par l'écran avec la fiche : matricule de pointage
    et nom d'usage (une badgeuse porte souvent le nom marital, pas le nom de famille)."""
    if not company_id or not roster:
        return roster
    ids = [e.id for e in roster]
    try:
        resp = (
            supabase.table("employees")
            .select("id, time_tracking_id, nom_usage")
            .in_("id", ids)
            .execute()
        )
    except Exception:
        return roster
    rows = {row["id"]: row for row in (resp.data or []) if row.get("id")}

    def _texte(row: dict | None, cle: str) -> str | None:
        return ((row or {}).get(cle) or "").strip() or None

    return [
        RosterEmployee(
            id=e.id,
            first_name=e.first_name,
            last_name=e.last_name,
            time_tracking_id=_texte(rows.get(e.id), "time_tracking_id") or e.time_tracking_id,
            usage_name=_texte(rows.get(e.id), "nom_usage") or e.usage_name,
        )
        for e in roster
    ]


__all__ = ["enrich_roster_time_tracking_ids"]
