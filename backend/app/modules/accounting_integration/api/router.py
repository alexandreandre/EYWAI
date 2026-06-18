"""Router API intégration comptable (RH + super-admin)."""

from __future__ import annotations

import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import get_current_user
from app.modules.exports.api.dependencies import get_active_company_id
from app.modules.accounting_integration.application import service
from app.modules.accounting_integration.schemas.responses import (
    AccountingConfigResponse,
    AccountingConfigUpdate,
    AccountingTransmissionsResponse,
    BulkCegidDossiersResponse,
    BulkCegidDossiersUpdate,
    ConnectionTestResponse,
    PlatformCatalogResponse,
    PlatformProviderEntry,
    PlatformProviderUpdate,
    ProvidersListResponse,
    TransmitComptaResult,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/accounting-integration", tags=["Intégration comptable"])
router_admin = APIRouter(
    prefix="/api/super-admin/accounting-integrations",
    tags=["Admin plateforme — Intégrations comptables"],
)


def _require_rh(current_user: User, company_id: str) -> None:
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès RH requis.")


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


@router.get("/config", response_model=AccountingConfigResponse)
async def get_accounting_config(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
) -> AccountingConfigResponse:
    _require_rh(current_user, company_id)
    return service.get_config(company_id)


@router.patch("/config", response_model=AccountingConfigResponse)
async def update_accounting_config(
    body: AccountingConfigUpdate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
) -> AccountingConfigResponse:
    _require_rh(current_user, company_id)
    try:
        return service.update_config(company_id, body)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_accounting_connection(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
) -> ConnectionTestResponse:
    _require_rh(current_user, company_id)
    return service.test_connection(company_id)


@router.get("/providers", response_model=ProvidersListResponse)
async def list_accounting_providers(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
) -> ProvidersListResponse:
    _require_rh(current_user, company_id)
    return service.list_providers_for_company(company_id)


@router.get("/transmissions", response_model=AccountingTransmissionsResponse)
async def list_accounting_transmissions(
    period: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
) -> AccountingTransmissionsResponse:
    _require_rh(current_user, company_id)
    return service.list_company_transmissions(
        company_id, period=period, status=status, limit=limit
    )


@router.post(
    "/transmissions/{transmission_id}/retry",
    response_model=TransmitComptaResult,
)
async def retry_accounting_transmission(
    transmission_id: str,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
) -> TransmitComptaResult:
    _require_rh(current_user, company_id)
    return service.retry_transmission(transmission_id, company_id)


# --- Super-admin -------------------------------------------------------------


@router_admin.get("/catalog", response_model=PlatformCatalogResponse)
async def get_platform_catalog(
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> PlatformCatalogResponse:
    return service.get_platform_catalog()


@router_admin.put(
    "/catalog/{provider_key}",
    response_model=PlatformProviderEntry,
)
async def update_platform_provider(
    provider_key: str,
    body: PlatformProviderUpdate,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> PlatformProviderEntry:
    try:
        return service.update_platform_provider(provider_key, body)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router_admin.post(
    "/catalog/{provider_key}/test-connection",
    response_model=ConnectionTestResponse,
)
async def admin_test_platform_accounting_connection(
    provider_key: str,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> ConnectionTestResponse:
    return service.test_platform_connection(provider_key)


@router_admin.post(
    "/companies/bulk-cegid-dossiers",
    response_model=BulkCegidDossiersResponse,
)
async def admin_bulk_update_cegid_dossiers(
    body: BulkCegidDossiersUpdate,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> BulkCegidDossiersResponse:
    try:
        return service.bulk_update_cegid_dossiers(body)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router_admin.get("/transmissions", response_model=AccountingTransmissionsResponse)
async def list_all_accounting_transmissions(
    company_id: Optional[str] = None,
    period: Optional[str] = None,
    status: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = 100,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> AccountingTransmissionsResponse:
    return service.list_all_transmissions(
        company_id=company_id,
        period=period,
        status=status,
        provider=provider,
        limit=limit,
    )


@router_admin.post(
    "/transmissions/{transmission_id}/retry",
    response_model=TransmitComptaResult,
)
async def admin_retry_transmission(
    transmission_id: str,
    company_id: str,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> TransmitComptaResult:
    return service.retry_transmission(transmission_id, company_id)


@router_admin.get(
    "/companies/{company_id}/config",
    response_model=AccountingConfigResponse,
)
async def admin_get_company_accounting_config(
    company_id: str,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> AccountingConfigResponse:
    return service.get_config(company_id)


@router_admin.patch(
    "/companies/{company_id}/config",
    response_model=AccountingConfigResponse,
)
async def admin_update_company_accounting_config(
    company_id: str,
    body: AccountingConfigUpdate,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> AccountingConfigResponse:
    try:
        return service.update_config(company_id, body)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e)) from e


@router_admin.post(
    "/companies/{company_id}/test-connection",
    response_model=ConnectionTestResponse,
)
async def admin_test_company_accounting_connection(
    company_id: str,
    _admin: Dict[str, Any] = Depends(_verify_super_admin),
) -> ConnectionTestResponse:
    return service.test_connection(company_id)
