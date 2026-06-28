"""Cas d'usage — emails RH pour demandes de congés."""

from __future__ import annotations

from typing import Any

from app.modules.absences.infrastructure import (
    leave_notification_settings_repository as repo,
)
from app.modules.absences.schemas.leave_settings import LeaveNotificationSettingsUpdate
from app.modules.absences.schemas.leave_settings_responses import (
    LeaveNotificationSettingsResponse,
)
from app.modules.employees.domain.rules import is_dsn_import_placeholder_email

ALLOWED_RECIPIENT_ROLES = ("admin", "rh", "collaborateur_rh")


def _clean_roles(raw: list[str] | None) -> list[str]:
    if raw is None:
        return list(repo.DEFAULT_LEAVE_NOTIFICATION_SETTINGS["recipient_roles"])
    seen: set[str] = set()
    roles: list[str] = []
    for role in raw:
        r = str(role).strip()
        if r in ALLOWED_RECIPIENT_ROLES and r not in seen:
            roles.append(r)
            seen.add(r)
    return roles


def _clean_emails(raw: list[str] | None) -> list[str]:
    if raw is None:
        return []
    seen: set[str] = set()
    emails: list[str] = []
    for item in raw:
        email = str(item).strip().lower()
        if not email or "@" not in email or is_dsn_import_placeholder_email(email):
            continue
        if email not in seen:
            emails.append(email)
            seen.add(email)
    return emails


def _to_response(
    company_id: str, data: dict[str, Any], configured: bool
) -> LeaveNotificationSettingsResponse:
    return LeaveNotificationSettingsResponse(
        company_id=company_id,
        enabled=bool(data.get("enabled", False)),
        notify_on_employee_request=bool(data.get("notify_on_employee_request", True)),
        notify_after_manager_approval=bool(
            data.get("notify_after_manager_approval", True)
        ),
        recipient_roles=_clean_roles(data.get("recipient_roles")),
        extra_recipient_emails=_clean_emails(data.get("extra_recipient_emails")),
        configured=configured,
    )


def get_settings(company_id: str) -> LeaveNotificationSettingsResponse:
    data, configured = repo.get_effective_settings(company_id)
    return _to_response(company_id, data, configured)


def update_settings(
    company_id: str,
    body: LeaveNotificationSettingsUpdate,
    *,
    updated_by: str | None = None,
) -> LeaveNotificationSettingsResponse:
    current = get_settings(company_id).model_dump()
    patch = body.model_dump(exclude_unset=True)
    current.update(patch)

    payload: dict[str, Any] = {
        "enabled": bool(current.get("enabled")),
        "notify_on_employee_request": bool(current.get("notify_on_employee_request")),
        "notify_after_manager_approval": bool(
            current.get("notify_after_manager_approval")
        ),
        "recipient_roles": _clean_roles(current.get("recipient_roles")),
        "extra_recipient_emails": _clean_emails(current.get("extra_recipient_emails")),
    }
    if updated_by:
        payload["updated_by"] = updated_by

    row = repo.upsert(company_id, payload)
    return _to_response(company_id, row, True)
