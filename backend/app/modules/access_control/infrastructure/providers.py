"""
Accès externes du module access_control.

Une seule responsabilité aujourd'hui : rattacher un salarié à sa société,
pour que require_employee_access puisse refuser un employee_id venu d'une
AUTRE société (faille IDOR inter-sociétés fermée le 23/08/2026).
"""

from __future__ import annotations

from typing import Optional

from app.core.database import supabase
from app.core.logging import get_logger

logger = get_logger("modules.access_control.providers")


def get_employee_company_id(employee_id: str) -> Optional[str]:
    """Société réelle d'un salarié — None si introuvable ou illisible.

    None est traité comme « hors périmètre » par l'appelant (fail-closed) :
    une panne de lecture ne doit jamais ouvrir l'accès.
    """
    try:
        response = (
            supabase.table("employees")
            .select("company_id")
            .eq("id", str(employee_id))
            .maybe_single()
            .execute()
        )
    except Exception:
        logger.warning(
            "Périmètre : société du salarié %s illisible", employee_id, exc_info=True
        )
        return None
    data = getattr(response, "data", None) if response else None
    if not data:
        return None
    company_id = data.get("company_id")
    return str(company_id) if company_id else None
