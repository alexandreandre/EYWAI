"""Accès au paramétrage DSN d'une société.

Une société sans ligne a un paramétrage vide : l'export signale ses manques par
``DsnSettings.manques()``. Une lecture qui échoue n'est pas une société vide (R-467) :
elle lève ``ParametrageDsnIllisible`` et l'export s'arrête au lieu de partir sans
SIRET d'URSSAF ni organismes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.database import supabase
from app.modules.dsn_export.domain.settings import (
    DsnSettings,
    depuis_dict,
    vers_dict,
)

logger = logging.getLogger(__name__)

TABLE = "company_dsn_settings"

MESSAGE_ILLISIBLE = (
    "Le paramétrage DSN de la société n'a pas pu être lu : aucun fichier n'est produit. "
    "Réessayez dans un instant."
)


class ParametrageDsnIllisible(ValueError):
    """La lecture du paramétrage DSN a échoué : rien ne se déclare sans lui (R-467)."""


def charger(company_id: str) -> DsnSettings:
    """Lit le paramétrage d'une société ; vide si la société n'en a pas encore."""
    try:
        reponse = (
            supabase.table(TABLE).select("*").eq("company_id", company_id).execute()
        )
    except Exception as exc:  # table absente, droits, réseau
        logger.warning("Paramétrage DSN illisible pour %s : %s", company_id, exc)
        raise ParametrageDsnIllisible(MESSAGE_ILLISIBLE) from exc
    lignes = reponse.data or []
    return depuis_dict(lignes[0] if lignes else None)


def enregistrer(
    company_id: str,
    settings: DsnSettings,
    *,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Écrit le paramétrage d'une société (insertion ou mise à jour)."""
    ligne = vers_dict(settings)
    ligne["company_id"] = company_id
    if updated_by:
        ligne["updated_by"] = updated_by
    reponse = supabase.table(TABLE).upsert(ligne, on_conflict="company_id").execute()
    return (reponse.data or [{}])[0]
