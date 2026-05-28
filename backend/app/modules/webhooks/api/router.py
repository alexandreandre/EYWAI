from __future__ import annotations

import traceback
from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.core.http_dependencies import require_active_company, require_rh_access
from app.core.security import get_current_user
from app.modules.exports.api.dependencies import get_active_company_id
from app.modules.users.schemas.responses import User
from app.modules.webhooks.application import service as webhook_service
from app.modules.webhooks.schemas.responses import (
    WebhookConfigOut,
    WebhookCreate,
    WebhookLogOut,
    WebhookTestResponse,
    WebhookUpdate,
)

router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


def _row_to_config_out(row: dict) -> WebhookConfigOut:
    return WebhookConfigOut(
        id=str(row["id"]),
        company_id=str(row["company_id"]),
        name=str(row["name"]),
        url=str(row["url"]),
        events=list(row.get("events") or []),
        is_active=bool(row.get("is_active", True)),
        last_triggered_at=row.get("last_triggered_at"),
        last_status_code=row.get("last_status_code"),
        created_at=row["created_at"],
    )


def _row_to_log_out(row: dict) -> WebhookLogOut:
    return WebhookLogOut(
        id=str(row["id"]),
        webhook_id=str(row["webhook_id"]),
        event_type=str(row["event_type"]),
        response_status=row.get("response_status"),
        duration_ms=row.get("duration_ms"),
        created_at=row["created_at"],
    )


@router.get("", response_model=List[WebhookConfigOut])
def list_webhooks(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    require_rh_access(current_user, company_id)
    try:
        rows = webhook_service.list_webhooks(company_id)
        return [_row_to_config_out(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("", response_model=WebhookConfigOut, status_code=201)
def create_webhook(
    body: WebhookCreate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    require_rh_access(current_user, company_id)
    try:
        row = webhook_service.create_webhook(
            company_id,
            {
                "name": body.name,
                "url": body.url,
                "secret": body.secret,
                "events": body.events,
            },
            created_by=str(current_user.id),
        )
        return _row_to_config_out(row)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{webhook_id}", response_model=WebhookConfigOut)
def update_webhook(
    webhook_id: str,
    body: WebhookUpdate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    require_rh_access(current_user, company_id)
    try:
        patch = body.model_dump(exclude_unset=True)
        if "url" in patch and patch["url"] is not None:
            patch["url"] = str(patch["url"])
        row = webhook_service.update_webhook(webhook_id, company_id, patch)
        return _row_to_config_out(row)
    except LookupError:
        raise HTTPException(status_code=404, detail="Webhook introuvable.") from None
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{webhook_id}", status_code=204)
def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    require_rh_access(current_user, company_id)
    try:
        ok = webhook_service.delete_webhook(webhook_id, company_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Webhook introuvable.")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{webhook_id}/test", response_model=WebhookTestResponse)
def test_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    require_rh_access(current_user, company_id)
    try:
        status, ok = webhook_service.send_test_webhook(webhook_id, company_id)
        return WebhookTestResponse(status_code=status, success=ok)
    except LookupError:
        raise HTTPException(status_code=404, detail="Webhook introuvable.") from None
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{webhook_id}/logs", response_model=List[WebhookLogOut])
def webhook_logs(
    webhook_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    require_rh_access(current_user, company_id)
    try:
        if not webhook_service.get_webhook(webhook_id, company_id):
            raise HTTPException(status_code=404, detail="Webhook introuvable.")
        rows = webhook_service.list_webhook_logs(webhook_id, company_id, limit=20)
        return [_row_to_log_out(r) for r in rows]
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e
