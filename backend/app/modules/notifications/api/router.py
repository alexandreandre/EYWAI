"""Routes /api/notifications — espace collaborateur."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.notifications.application import queries as notification_queries
from app.modules.notifications.application.employee_scope import (
    resolve_employee_id_for_notifications,
)
from app.modules.notifications.schemas.responses import NotificationResponse, UnreadCountResponse
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _company_id(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(cid)


def _employee_scope_or_403(user: User, company_id: str) -> str:
    """Résolution employé — id, user_id ou email."""
    eid = resolve_employee_id_for_notifications(
        str(user.id), company_id, user_email=user.email
    )
    if not eid:
        raise HTTPException(
            status_code=403,
            detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
        )
    return str(eid)


def _employee_id_for_notifications_read(user: User, company_id: str) -> str | None:
    """GET liste / compteur : pas d'employé → vide silencieux (pas 403/500)."""
    return resolve_employee_id_for_notifications(
        str(user.id), company_id, user_email=user.email
    )


def _row_to_response(row: Dict[str, Any]) -> NotificationResponse:
    return NotificationResponse(
        id=str(row["id"]),
        employee_id=str(row["employee_id"]) if row.get("employee_id") else None,
        company_id=str(row["company_id"]),
        type=str(row.get("type") or ""),
        message=str(row.get("message") or ""),
        is_read=bool(row.get("is_read")),
        created_at=row["created_at"],
    )


@router.get("", response_model=List[NotificationResponse])
def list_notifications(
    current_user: User = Depends(get_current_user),
) -> List[NotificationResponse]:
    cid = _company_id(current_user)
    employee_id = _employee_id_for_notifications_read(current_user, cid)
    if not employee_id:
        return []
    rows = notification_queries.list_for_employee(employee_id, cid, limit=20)
    return [_row_to_response(r) for r in rows]


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(current_user: User = Depends(get_current_user)) -> UnreadCountResponse:
    cid = _company_id(current_user)
    employee_id = _employee_id_for_notifications_read(current_user, cid)
    if not employee_id:
        return UnreadCountResponse(count=0)
    n = notification_queries.unread_count(employee_id, cid)
    return UnreadCountResponse(count=n)


@router.put("/read-all")
def mark_all_read(current_user: User = Depends(get_current_user)) -> dict:
    cid = _company_id(current_user)
    employee_id = _employee_scope_or_403(current_user, cid)
    notification_queries.mark_all_as_read(employee_id, cid)
    return {"success": True}


@router.put("/{notification_id}/read")
def mark_one_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    cid = _company_id(current_user)
    employee_id = _employee_scope_or_403(current_user, cid)
    notification_queries.mark_as_read(notification_id, employee_id)
    return {"success": True}
