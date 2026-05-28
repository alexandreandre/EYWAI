"""Requêtes lecture seule — journal d'audit."""

from __future__ import annotations

from typing import Any, Optional

from app.modules.audit.infrastructure.repository import audit_repository


def list_audit_logs_query(
    company_id: str,
    *,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    user_id: Optional[str] = None,
    created_after: Optional[str] = None,
    created_before: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return audit_repository.list_logs(
        company_id,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )
