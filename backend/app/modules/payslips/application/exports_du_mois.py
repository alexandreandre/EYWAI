"""Les exports déjà faits pour le mois d'un bulletin.

Corriger un bulletin après avoir sorti le journal de paie, le virement ou les
écritures comptables laisse ces fichiers faux, sans que rien ne le rappelle
(audit du 28/09). On ne bloque pas : on le dit sur l'écran du bulletin.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import supabase
from app.modules.exports.application.scheduled_exports import EXPORT_TYPE_LABELS

logger = logging.getLogger(__name__)


def exports_du_mois(company_id: str, year: int, month: int) -> list[dict[str, Any]]:
    """Un export par type, le plus récent, du plus ancien au plus récent."""
    try:
        r = (
            supabase.table("exports_history")
            .select("export_type, generated_at")
            .match(
                {
                    "company_id": str(company_id),
                    "period": f"{int(year):04d}-{int(month):02d}",
                    "status": "generated",
                }
            )
            .execute()
        )
    except Exception:  # noqa: BLE001 — une aide à l'écran, jamais une erreur de lecture
        logger.warning("Exports du mois illisibles", exc_info=True)
        return []
    derniers: dict[str, str] = {}
    for ligne in r.data or []:
        type_, date = str(ligne.get("export_type") or ""), str(ligne.get("generated_at") or "")
        if type_ and date > derniers.get(type_, ""):
            derniers[type_] = date
    return [
        {"type": type_, "libelle": EXPORT_TYPE_LABELS.get(type_, type_), "date": date}
        for type_, date in sorted(derniers.items(), key=lambda couple: couple[1])
    ]
