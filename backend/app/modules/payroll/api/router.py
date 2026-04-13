"""Router API — simulation paie (bulletin, arrêt maladie, etc.)."""

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.modules.payroll.application.simulation_arret_maladie import (
    run_simulation_arret_maladie,
)
from app.modules.payroll.schemas.requests import SimulationArretMaladieRequest
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/simulation", tags=["Simulation paie"])


@router.post("/arret-maladie")
def simulation_arret_maladie(
    body: SimulationArretMaladieRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Simulation maintien / IJSS pour un arrêt maladie (même moteur que le bulletin).
    Réservé aux profils avec accès RH sur l'entreprise active.
    """
    try:
        return run_simulation_arret_maladie(body, current_user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception:
        traceback.print_exc()
        raise HTTPException(
            status_code=500, detail="Erreur lors de la simulation arrêt maladie."
        ) from None
