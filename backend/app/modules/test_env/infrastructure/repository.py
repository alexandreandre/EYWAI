"""Persistance — journal des resynchros de l'environnement de test."""

from __future__ import annotations

from typing import Optional

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger("modules.test_env.repository")

TABLE = "test_env_refresh_log"


def lire_derniere_resynchro() -> Optional[str]:
    """
    Date de la dernière resynchro réussie, ou None.

    La table est recréée à chaque resynchro par le script de neutralisation :
    tant qu'aucune copie n'a tourné, elle est absente. Ce n'est pas une erreur,
    l'interface affiche alors « jamais ».
    """
    try:
        res = (
            supabase.table(TABLE)
            .select("finished_at")
            .order("finished_at", desc=True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0]["finished_at"]
    except Exception:
        logger.warning("Journal de resynchro illisible", exc_info=True)
    return None
