"""
Router API rates : appelle uniquement l'application du module.

Aucune logique métier : validation éventuelle, appel application, retour réponse.
Comportement HTTP identique au legacy (GET /all, 404 si vide, 500 sur erreur).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from app.modules.rates.api.dependencies import get_all_rates_reader
from app.modules.rates.application import get_all_rates, IAllRatesReader

router = APIRouter(tags=["Rates"])


@router.get("/all")
async def get_all_rates_endpoint(
    reader: IAllRatesReader = Depends(get_all_rates_reader),
) -> dict:
    """
    Récupère toutes les configurations actives de taux (payroll_config).
    Regroupe par config_key (version la plus récente). Comportement identique au legacy.
    """
    try:
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
