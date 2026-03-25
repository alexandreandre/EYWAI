"""
Requêtes Supabase pour rib_alerts (table rib_alerts + lecture employees pour doublons IBAN).

Logique DB extraite du repository ; comportement strictement identique au legacy.
Aucune dépendance FastAPI. Uniquement app.core.database et app.shared.utils.iban.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from app.core.database import supabase
from app.shared.utils.iban import normalize_iban

_SELECT_COLUMNS = (
    "id, company_id, employee_id, alert_type, severity, title, message, details, "
    "is_read, is_resolved, resolved_at, resolution_note, created_at"
)


def list_rib_alerts_rows(
    company_id: str,
    *,
    is_read: Optional[bool] = None,
    is_resolved: Optional[bool] = None,
    alert_type: Optional[str] = None,
    employee_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Liste les lignes rib_alerts avec filtres. Retourne (data, total). Comportement identique au router legacy."""
    query = (
        supabase.table("rib_alerts")
        .select(_SELECT_COLUMNS, count="exact")
        .eq("company_id", company_id)
    )
    if is_read is not None:
        query = query.eq("is_read", is_read)
    if is_resolved is not None:
        query = query.eq("is_resolved", is_resolved)
    if alert_type:
        query = query.eq("alert_type", alert_type)
    if employee_id:
        query = query.eq("employee_id", employee_id)
    result = (
        query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    )
    data = result.data or []
    total = (
        result.count
        if hasattr(result, "count") and result.count is not None
        else len(data)
    )
    return (data, total)


def get_rib_alert_row_by_id(alert_id: str, company_id: str) -> Optional[dict[str, Any]]:
    """Récupère une ligne rib_alert par id et company_id. None si non trouvée."""
    result = (
        supabase.table("rib_alerts")
        .select(_SELECT_COLUMNS)
        .eq("id", alert_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return result.data if result.data is not None else None


def update_rib_alert_read(alert_id: str, company_id: str) -> bool:
    """Marque une alerte comme lue. Retourne True si au moins une ligne mise à jour."""
    result = (
        supabase.table("rib_alerts")
        .update({"is_read": True})
        .eq("id", alert_id)
        .eq("company_id", company_id)
        .execute()
    )
    return bool(result.data)


def update_rib_alert_resolve(
    alert_id: str,
    company_id: str,
    resolved_by: str,
    resolution_note: Optional[str] = None,
) -> bool:
    """Marque une alerte comme résolue. Retourne True si au moins une ligne mise à jour. Comportement identique au legacy."""
    update_data: dict[str, Any] = {
        "is_resolved": True,
        "is_read": True,
        "resolved_at": datetime.utcnow().isoformat() + "Z",
        "resolved_by": resolved_by,
    }
    if resolution_note is not None:
        update_data["resolution_note"] = resolution_note
    result = (
        supabase.table("rib_alerts")
        .update(update_data)
        .eq("id", alert_id)
        .eq("company_id", company_id)
        .execute()
    )
    return bool(result.data)


def insert_rib_alert(payload: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Insère une alerte. Retourne la ligne insérée ou None en cas d’échec."""
    result = supabase.table("rib_alerts").insert(payload).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None


def get_duplicate_iban_employees(
    company_id: str,
    iban_normalise: str,
    exclude_employee_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Liste les employés de la même entreprise ayant le même IBAN (déjà normalisé).
    Retourne une liste de dicts { id, first_name, last_name }. Comportement identique au legacy check_duplicate_iban.
    """
    if not iban_normalise:
        return []
    response = (
        supabase.table("employees")
        .select("id, first_name, last_name, coordonnees_bancaires")
        .eq("company_id", company_id)
        .execute()
    )
    if not response.data:
        return []
    duplicates: list[dict[str, Any]] = []
    for row in response.data:
        if exclude_employee_id and str(row.get("id")) == str(exclude_employee_id):
            continue
        coord = row.get("coordonnees_bancaires")
        if isinstance(coord, str):
            try:
                coord = json.loads(coord) if coord else {}
            except Exception:
                coord = {}
        if not isinstance(coord, dict):
            continue
        emp_iban = (coord.get("iban") or "").strip()
        if not emp_iban:
            continue
        if normalize_iban(emp_iban) == iban_normalise:
            duplicates.append(
                {
                    "id": row.get("id"),
                    "first_name": row.get("first_name") or "",
                    "last_name": row.get("last_name") or "",
                }
            )
    return duplicates
