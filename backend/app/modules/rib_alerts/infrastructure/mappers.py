"""
Mappers rib_alerts : row DB <-> entité domain, entité -> dict réponse API.

Comportement identique au legacy (colonnes table rib_alerts, format réponse API).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.modules.rib_alerts.domain.entities import RibAlert


def _parse_optional_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    return None


def row_to_rib_alert(row: dict[str, Any]) -> RibAlert:
    """Convertit une ligne Supabase (table rib_alerts) en entité RibAlert."""
    return RibAlert(
        id=str(row["id"]) if row.get("id") is not None else None,
        company_id=str(row["company_id"]) if row.get("company_id") is not None else "",
        employee_id=str(row["employee_id"])
        if row.get("employee_id") is not None
        else None,
        alert_type=str(row.get("alert_type") or ""),
        severity=str(row.get("severity") or "warning"),
        title=str(row.get("title") or ""),
        message=str(row.get("message") or ""),
        details=dict(row["details"]) if isinstance(row.get("details"), dict) else {},
        is_read=bool(row.get("is_read", False)),
        is_resolved=bool(row.get("is_resolved", False)),
        resolved_at=_parse_optional_datetime(row.get("resolved_at")),
        resolution_note=str(row["resolution_note"])
        if row.get("resolution_note") is not None
        else None,
        resolved_by=str(row["resolved_by"])
        if row.get("resolved_by") is not None
        else None,
        created_at=_parse_optional_datetime(row.get("created_at")),
    )


def rib_alert_to_response_dict(alert: RibAlert) -> dict[str, Any]:
    """Convertit une entité RibAlert en dict pour la réponse API (GET list). Comportement identique au legacy."""
    return {
        "id": alert.id,
        "company_id": alert.company_id,
        "employee_id": alert.employee_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "details": alert.details,
        "is_read": alert.is_read,
        "is_resolved": alert.is_resolved,
        "resolved_at": alert.resolved_at.isoformat() + "Z"
        if alert.resolved_at
        else None,
        "resolution_note": alert.resolution_note,
        "created_at": alert.created_at.isoformat() + "Z" if alert.created_at else None,
    }
