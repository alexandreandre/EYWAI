from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.audit.infrastructure.repository import audit_repository
from app.modules.audit.schemas.responses import AuditLogEntry
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/audit", tags=["Audit"])

_log = logging.getLogger(__name__)


def _require_rh_company_context(current_user: User) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return str(company_id)


@router.get("/logs", response_model=List[AuditLogEntry])
def list_audit_logs_route(
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    created_after: Optional[str] = Query(
        None, description="ISO date ou datetime (filtre >=)"
    ),
    created_before: Optional[str] = Query(
        None, description="ISO date ou datetime (filtre <=)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """Journal d'audit pour l'entreprise active (profil RH)."""
    company_id = _require_rh_company_context(current_user)
    try:
        rows = audit_repository.list_logs(
            company_id,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            created_after=created_after,
            created_before=created_before,
            limit=limit,
            offset=offset,
        )
        out: List[AuditLogEntry] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = row.get("company_id")
            if cid is None:
                continue
            out.append(
                AuditLogEntry(
                    id=str(row.get("id") or ""),
                    company_id=str(cid),
                    user_id=str(row["user_id"]) if row.get("user_id") else None,
                    user_email=row.get("user_email"),
                    action=str(row.get("action") or ""),
                    resource_type=str(row.get("resource_type") or ""),
                    resource_id=str(row["resource_id"])
                    if row.get("resource_id") is not None
                    else None,
                    details=row.get("details")
                    if isinstance(row.get("details"), dict)
                    else None,
                    ip_address=row.get("ip_address"),
                    created_at=row["created_at"],
                )
            )
        return out
    except HTTPException:
        raise
    except Exception as e:
        _log.exception("audit logs: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
