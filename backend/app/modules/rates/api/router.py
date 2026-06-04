"""
Router API rates : appelle uniquement l'application du module.

Aucune logique métier : validation éventuelle, appel application, retour réponse.
Comportement HTTP identique au legacy (GET /all, 404 si vide, 500 sur erreur).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User
from app.modules.rates.api.dependencies import get_all_rates_reader, get_rates_writer
from app.modules.rates.application import (
    IAllRatesReader,
    IRatesWriter,
    apply_manual_rate_override,
    cancel_rates_sync,
    get_all_rates,
    get_rates_sync_sources_manifest,
    get_rates_sync_status,
    start_rates_sync,
)
from app.modules.rates.schemas.requests import ManualRateUpdateRequest, RatesSyncRequest

router = APIRouter(tags=["Rates"])

_ERR_RH_REQUIRED = "Accès réservé aux RH et administrateurs."
_ERR_ADMIN_REQUIRED = "Saisie manuelle réservée aux administrateurs plateforme."


def _require_rh_or_admin(current_user: User) -> None:
    if current_user.is_platform_admin:
        return
    active_company_id = current_user.active_company_id
    if not active_company_id or not current_user.has_rh_access_in_company(active_company_id):
        raise HTTPException(status_code=403, detail=_ERR_RH_REQUIRED)


def _require_platform_admin(current_user: User) -> None:
    if not current_user.is_platform_admin:
        raise HTTPException(status_code=403, detail=_ERR_ADMIN_REQUIRED)


@router.get("/all")
async def get_all_rates_endpoint(
    reader: IAllRatesReader = Depends(get_all_rates_reader),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Récupère toutes les configurations actives de taux (payroll_config).
    Regroupe par config_key (version la plus récente). Comportement identique au legacy.
    """
    try:
        _require_rh_or_admin(current_user)
        result = get_all_rates(reader)
        if not result:
            raise HTTPException(
                status_code=404,
                detail="Aucune configuration active trouvée.",
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Erreur lors de la récupération des taux : %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual")
async def manual_rate_update_endpoint(
    body: ManualRateUpdateRequest,
    writer: IRatesWriter = Depends(get_rates_writer),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Saisie manuelle d'un bloc de taux (versioning immuable de payroll_config).

    Réservé aux administrateurs plateforme. Désactive la version active et insère
    une nouvelle version ; no-op horodaté si le contenu est identique.
    """
    try:
        _require_platform_admin(current_user)
        actor_label = getattr(current_user, "email", None) or str(current_user.id)
        result = apply_manual_rate_override(
            writer,
            config_key=body.config_key,
            config_data=body.config_data,
            actor_label=actor_label,
            comment=body.comment,
            source_links=body.source_links,
        )
        return {"success": True, **result}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logging.exception("❌ Erreur saisie manuelle taux : %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/sources")
async def get_rates_sync_sources_endpoint(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Manifeste des sources mettables à jour (par catégorie et par cotisation)."""
    try:
        _require_rh_or_admin(current_user)
        return get_rates_sync_sources_manifest()
    except HTTPException:
        raise
    except Exception as e:
        logging.exception("❌ Erreur manifeste sync taux : %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync")
async def start_rates_sync_endpoint(
    background_tasks: BackgroundTasks,
    body: RatesSyncRequest | None = None,
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Lance la mise à jour réglementaire (globale ou ciblée par rate_key / source / cotisation).
    Réservé aux RH / administrateurs.
    """
    try:
        _require_rh_or_admin(current_user)
        payload = body or RatesSyncRequest()
        return start_rates_sync(
            triggered_by=current_user.id,
            background_task_fn=background_tasks.add_task,
            rate_keys=payload.rate_keys,
            source_keys=payload.source_keys,
            cotisation_ids=payload.cotisation_ids,
        )
    except HTTPException:
        raise
    except ValueError as e:
        msg = str(e)
        if "déjà en cours" in msg.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        if "Aucune source" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    except Exception as e:
        logging.exception("❌ Erreur lors du lancement de la sync taux : %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync/{sync_id}/cancel")
async def cancel_rates_sync_endpoint(
    sync_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Annule une synchronisation en cours (jobs scraping + verrous sources)."""
    try:
        _require_rh_or_admin(current_user)
        return cancel_rates_sync(sync_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logging.exception("❌ Erreur annulation sync taux %s : %s", sync_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/{sync_id}/status")
async def get_rates_sync_status_endpoint(
    sync_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Suivi d'avancement d'une synchronisation des taux."""
    try:
        _require_rh_or_admin(current_user)
        return get_rates_sync_status(sync_id)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logging.exception("❌ Erreur statut sync taux %s : %s", sync_id, e)
        raise HTTPException(status_code=500, detail=str(e))
