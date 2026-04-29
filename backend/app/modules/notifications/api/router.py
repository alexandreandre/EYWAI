"""Routes /api/notifications — espace collaborateur."""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.documents.application.queries import get_employee_id_for_user_scope
from app.modules.notifications.infrastructure.repository import notifications_repository
from app.modules.notifications.schemas.responses import NotificationResponse, UnreadCountResponse
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


def _company_id(user: User) -> str:
    cid = user.active_company_id
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(cid)


def _employee_scope_or_403(user: User, company_id: str) -> str:
    """Résolution employé — même pattern que documents / certifications."""
    eid = get_employee_id_for_user_scope(str(user.id), company_id)
    if not eid:
        raise HTTPException(
            status_code=403,
            detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
        )
    return str(eid)


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
    employee_id = _employee_scope_or_403(current_user, cid)
    rows = notifications_repository.get_for_employee(employee_id, cid, limit=20)
    return [_row_to_response(r) for r in rows]


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(current_user: User = Depends(get_current_user)) -> UnreadCountResponse:
    cid = _company_id(current_user)
    employee_id = _employee_scope_or_403(current_user, cid)
    n = notifications_repository.get_unread_count(employee_id, cid)
    return UnreadCountResponse(count=n)


@router.put("/read-all")
def mark_all_read(current_user: User = Depends(get_current_user)) -> dict:
    cid = _company_id(current_user)
    employee_id = _employee_scope_or_403(current_user, cid)
    notifications_repository.mark_all_as_read(employee_id, cid)
    return {"success": True}


@router.put("/{notification_id}/read")
def mark_one_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    cid = _company_id(current_user)
    employee_id = _employee_scope_or_403(current_user, cid)
    notifications_repository.mark_as_read(notification_id, employee_id)
    return {"success": True}

