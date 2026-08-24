"""Router API — configuration e-mail plateforme (super-admin)."""

from __future__ import annotations

import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.modules.platform_settings.application import service
from app.modules.platform_settings.schemas import (
    EmailSettingsResponse,
    EmailSettingsTestRequest,
    EmailSettingsUpdate,
    EmailTestResponse,
)
from app.modules.users.schemas.responses import User

router = APIRouter(
    prefix="/api/super-admin/email-settings",
    tags=["Admin plateforme"],
)


async def _verify_super_admin(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    from app.modules.super_admin.application.service import (
        SuperAdminAccessError,
        verify_super_admin_and_return_row,
    )

    try:
        return verify_super_admin_and_return_row(str(current_user.id))
    except SuperAdminAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Erreur lors de la vérification : {e}",
        ) from e


@router.get("", response_model=EmailSettingsResponse)
def get_email_settings(
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
):
    try:
        return service.get_email_settings()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("", response_model=EmailSettingsResponse)
def update_email_settings(
    body: EmailSettingsUpdate,
    current_user: User = Depends(get_current_user),
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
):
    try:
        return service.update_email_settings(body, updated_by=str(current_user.id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/test", response_model=EmailTestResponse)
def test_email_settings(
    body: EmailSettingsTestRequest,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
):
    try:
        return service.send_test_email(body.to_email)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e
