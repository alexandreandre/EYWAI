"""Lecture du jour de mise à disposition des bulletins réglé par la société."""

from __future__ import annotations

import logging

from app.core.database import supabase
from app.modules.payslips.domain.mise_a_disposition import (
    JOUR_PAR_DEFAUT,
    jour_de_mise_a_disposition,
)

logger = logging.getLogger(__name__)


def jour_de_la_societe(company_id: str | None) -> int:
    """Le jour réglé ; le 1er du mois suivant si la lecture échoue (le plus prudent :
    un bulletin n'est pas montré trop tôt)."""
    if not company_id:
        return JOUR_PAR_DEFAUT
    try:
        r = (
            supabase.table("companies")
            .select("settings")
            .eq("id", company_id)
            .maybe_single()
            .execute()
        )
    except Exception:
        logger.exception("[remise] Réglage de mise à disposition illisible pour %s", company_id)
        return JOUR_PAR_DEFAUT
    return jour_de_mise_a_disposition(((r.data if r else None) or {}).get("settings"))
