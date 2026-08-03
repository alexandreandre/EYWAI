"""Accès au paramétrage DSN d'une société.

Tant que la table n'est pas déployée, la lecture retourne un paramétrage vide
plutôt que de faire échouer la génération : l'export signale alors ses manques
par ``DsnSettings.manques()``.
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


def charger(company_id: str) -> DsnSettings:
    """Lit le paramétrage d'une société, vide si absent ou table non déployée."""
    try:
        reponse = (
            supabase.table(TABLE).select("*").eq("company_id", company_id).execute()
        )
    except Exception as exc:  # table absente, droits, réseau
        logger.warning("Paramétrage DSN illisible pour %s : %s", company_id, exc)
        return DsnSettings()
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
