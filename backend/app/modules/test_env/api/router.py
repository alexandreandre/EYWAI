"""Pilotage de la resynchro de l'environnement de test."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core import settings
from app.modules.super_admin.api.router import verify_super_admin
from app.modules.test_env.application.service import (
    declencher_workflow_resynchro,
    lire_derniere_resynchro,
)
from app.modules.test_env.domain.exceptions import (
    RefreshDispatchRefused,
    RefreshNotConfigured,
)

router = APIRouter(prefix="/api/test-env", tags=["Environnement de test"])


@router.get("/status")
def statut() -> dict:
    """Indique s'il s'agit de l'environnement de test et la date de dernière resynchro."""
    if not settings.is_test_environment():
        return {"is_test": False, "last_refresh_at": None}
    return {"is_test": True, "last_refresh_at": lire_derniere_resynchro()}


@router.post("/refresh")
def resynchroniser(
    _super_admin: dict[str, Any] = Depends(verify_super_admin),
) -> dict:
    """
    Déclenche une resynchro depuis la production.

    Disponible uniquement dans l'environnement de test, et aux super admins :
    la resynchro remplace toute la base de test, qui porte une vraie paie
    depuis septembre 2026. Le workflow exige en plus une confirmation tapée et
    refuse d'écraser une base porteuse d'une reprise de paie.
    """
    if not settings.is_test_environment():
        raise HTTPException(
            status_code=403,
            detail="La resynchro n'est disponible que dans l'environnement de test.",
        )
    try:
        declencher_workflow_resynchro()
    except RefreshNotConfigured as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    except RefreshDispatchRefused as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"triggered": True}
