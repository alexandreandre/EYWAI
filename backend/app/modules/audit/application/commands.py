"""Commandes audit — façade application (pas d'import infra depuis les routers)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.audit.infrastructure.repository import audit_repository


def log_audit_event(
    company_id: str,
    user_id: Optional[str],
    user_email: Optional[str],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    audit_repository.log(
        company_id,
        user_id,
        user_email,
        action,
        resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
