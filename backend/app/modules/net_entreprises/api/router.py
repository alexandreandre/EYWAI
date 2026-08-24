"""Router API net_entreprises (prefix=/api/net-entreprises).

Router fin : auth RH + header X-Active-Company, délégation au service.
Aucun secret n'est jamais renvoyé.
"""

from __future__ import annotations

import traceback
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from typing import Any, Dict

from fastapi import status

from app.core.security import get_current_user
from app.modules.exports.api.dependencies import get_active_company_id
from app.modules.net_entreprises.application import service
from app.modules.net_entreprises.schemas import (
    AdminDSNTransmissionsResponse,
    ConnectionTestResponse,
    DSNTransmissionEntry,
    DSNTransmissionsResponse,
    MarkTransmittedRequest,
    NetEntreprisesConfigResponse,
    NetEntreprisesConfigUpdate,
)
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/net-entreprises", tags=["Net-entreprises"])
router_admin = APIRouter(
    prefix="/api/super-admin/net-entreprises", tags=["Admin plateforme"]
)


async def _verify_super_admin(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    # Import paresseux : le module super_admin déclenche une lourde chaîne d'imports
    # (scraping) sensible à l'ordre de chargement. On l'importe au moment de l'appel.
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


def _require_rh(current_user: User, company_id: str) -> None:
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(status_code=403, detail="Accès réservé au profil RH.")


@router.get("/config", response_model=NetEntreprisesConfigResponse)
def get_net_entreprises_config(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Config de connexion Net-entreprises de l'entreprise active (sans secret)."""
    _require_rh(current_user, company_id)
    try:
        return service.get_config(company_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config", response_model=NetEntreprisesConfigResponse)
def update_net_entreprises_config(
    body: NetEntreprisesConfigUpdate,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Crée/met à jour la config (secret stocké côté serveur, jamais relu)."""
    _require_rh(current_user, company_id)
    try:
        return service.update_config(
            company_id, body.model_dump(exclude_unset=True), str(current_user.id)
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/config/test-connection", response_model=ConnectionTestResponse)
def test_net_entreprises_connection(
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Teste la connexion (renvoie un état propre, ne plante jamais)."""
    _require_rh(current_user, company_id)
    return service.test_connection(company_id)


@router.get("/transmissions", response_model=DSNTransmissionsResponse)
def list_net_entreprises_transmissions(
    period: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Historique des transmissions DSN de l'entreprise active."""
    _require_rh(current_user, company_id)
    try:
        return service.list_transmissions(company_id, period)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/transmissions/{transmission_id}/mark-transmitted",
    response_model=DSNTransmissionEntry,
)
def mark_transmission_transmitted(
    transmission_id: str,
    body: MarkTransmittedRequest,
    current_user: User = Depends(get_current_user),
    company_id: str = Depends(get_active_company_id),
):
    """Mode manuel : confirme le dépôt et enregistre le numéro d'accusé."""
    _require_rh(current_user, company_id)
    try:
        return service.mark_transmitted(
            company_id, transmission_id, body.net_entreprises_ref
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ----- Suivi & pilotage plateforme (super-admin) -----


@router_admin.get("/transmissions", response_model=AdminDSNTransmissionsResponse)
def admin_list_transmissions(
    status_filter: Optional[str] = None,
    period: Optional[str] = None,
    super_admin: Dict[str, Any] = Depends(_verify_super_admin),
):
    """Suivi de toutes les transmissions DSN (toutes entreprises) + compteurs."""
    try:
        return service.list_all_transmissions_admin(status=status_filter, period=period)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router_admin.get(
    "/config/{target_company_id}", response_model=NetEntreprisesConfigResponse
)
def admin_get_config(
    target_company_id: str,
    super_admin: Dict[str, Any] = Depends(_verify_super_admin),
):
    """Config Net-entreprises d'une entreprise (lecture pilotage plateforme)."""
    try:
        return service.get_config(target_company_id)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router_admin.put(
    "/config/{target_company_id}", response_model=NetEntreprisesConfigResponse
)
def admin_update_config(
    target_company_id: str,
    body: NetEntreprisesConfigUpdate,
    super_admin: Dict[str, Any] = Depends(_verify_super_admin),
):
    """Override de la config Net-entreprises d'une entreprise (pilotage plateforme)."""
    try:
        return service.update_config(
            target_company_id,
            body.model_dump(exclude_unset=True),
            str(super_admin.get("user_id") or super_admin.get("id") or ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
