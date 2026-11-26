"""Lecture des congés parentaux d'un salarié (ancienneté pour moitié, L1225-54).

Un seul calcul, partagé : `shared.domain.conge_parental.jours_d_anciennete_neutralises`
sur les demandes validées. Ce module ne fait que les lire."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.shared.domain.conge_parental import (
    SOUS_TYPE_CONGE_PARENTAL,
    TYPE_DEMANDE_CONGE_PARENTAL,
    jours_d_anciennete_neutralises,
)


def conges_parentaux_du_salarie(employee_id: str | None, client: Any = None) -> list[dict]:
    """Les congés parentaux validés du salarié (type, sous-type, jours)."""
    if not employee_id:
        return []
    if client is None:
        from app.core.database import supabase as client
    res = (
        client.table("absence_requests")
        .select("type, event_subtype, status, selected_days")
        .eq("employee_id", str(employee_id))
        .eq("status", "validated")
        .eq("event_subtype", SOUS_TYPE_CONGE_PARENTAL)
        .execute()
    )
    return [r for r in (getattr(res, "data", None) or []) if r.get("type") == TYPE_DEMANDE_CONGE_PARENTAL]


def jours_neutralises_du_salarie(
    employee_id: str | None, jusqu_au: date, client: Any = None, depuis: date | None = None
) -> int:
    """Jours d'ancienneté que les congés parentaux validés ne donnent pas."""
    if not employee_id:
        return 0
    return jours_d_anciennete_neutralises(
        conges_parentaux_du_salarie(employee_id, client), jusqu_au, depuis
    )
