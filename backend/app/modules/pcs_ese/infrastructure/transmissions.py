"""La dernière DSN mensuelle de la société partie chez net-entreprises."""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, Optional

from app.core.database import supabase

logger = logging.getLogger(__name__)

#: Envoyée, reçue, ou remise pour un dépôt à la main (Martine n'a pas d'accès API) : déclarée.
#: « generated » (fichier pas encore envoyé) et « rejected » ne comptent pas.
STATUTS_DECLARES = ("sent", "acknowledged", "manual")


def periode_la_plus_recente(lignes: Iterable[Dict[str, Any]]) -> Optional[str]:
    periodes = [
        str(ligne.get("period") or "")[:7]
        for ligne in lignes
        if ligne.get("status") in STATUTS_DECLARES
        and str(ligne.get("dsn_type") or "dsn_mensuelle").startswith("dsn_mensuelle")
        and ligne.get("period")
    ]
    return max(periodes) if periodes else None


def derniere_periode_deposee(company_id: str) -> Optional[str]:
    """`None` si rien n'est parti, ou si la lecture échoue : le bloc repart plutôt que de manquer."""
    try:
        r = (
            supabase.table("dsn_transmissions")
            .select("period, dsn_type, status")
            .eq("company_id", company_id)
            .execute()
        )
    except Exception:
        logger.exception("Lecture dsn_transmissions échouée (company=%s)", company_id)
        return None
    return periode_la_plus_recente(r.data or [])
