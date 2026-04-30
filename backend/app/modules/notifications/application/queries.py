"""Lecture des notifications — délégation au repository."""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.notifications.infrastructure.repository import notifications_repository


def list_for_employee(
    employee_id: str,
    company_id: str,
    *,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    return notifications_repository.get_for_employee(employee_id, company_id, limit=limit)


def unread_count(employee_id: str, company_id: str) -> int:
    return notifications_repository.get_unread_count(employee_id, company_id)


def mark_all_as_read(employee_id: str, company_id: str) -> None:
    notifications_repository.mark_all_as_read(employee_id, company_id)


def mark_as_read(notification_id: str, employee_id: str) -> None:
    notifications_repository.mark_as_read(notification_id, employee_id)
