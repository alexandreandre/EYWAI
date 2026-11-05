"""Les mois dont une DSN mensuelle de la société est partie chez net-entreprises."""

from __future__ import annotations

import logging
from typing import Any, Dict, FrozenSet, Iterable

from app.core.database import supabase

logger = logging.getLogger(__name__)

#: Envoyée, reçue, ou remise pour un dépôt à la main (Martine n'a pas d'accès API : chaque
#: génération est enregistrée « manual »). « generated » et « rejected » ne comptent pas.
STATUTS_DECLARES = ("sent", "acknowledged", "manual")


def periodes_declarees(lignes: Iterable[Dict[str, Any]]) -> FrozenSet[str]:
    return frozenset(
        str(ligne.get("period") or "")[:7]
        for ligne in lignes
        if ligne.get("status") in STATUTS_DECLARES
        and str(ligne.get("dsn_type") or "dsn_mensuelle").startswith("dsn_mensuelle")
        and ligne.get("period")
    )


def periodes_deposees(company_id: str) -> FrozenSet[str]:
    """Aucune si la lecture échoue : le bloc repart plutôt que de manquer."""
    try:
        r = (
            supabase.table("dsn_transmissions")
            .select("period, dsn_type, status")
            .eq("company_id", company_id)
            .execute()
        )
        lignes = r.data if isinstance(r.data, list) else []
        return periodes_declarees(ligne for ligne in lignes if isinstance(ligne, dict))
    except Exception:
        logger.exception("Lecture dsn_transmissions échouée (company=%s)", company_id)
        return frozenset()
