"""Les exports déjà faits pour le mois d'un bulletin.

Corriger un bulletin après avoir sorti le journal de paie, le virement ou les
écritures comptables laisse ces fichiers faux, sans que rien ne le rappelle
(audit du 28/09). On ne bloque pas : on le dit sur l'écran du bulletin. Un
export fait avant le dernier calcul (ou la dernière suppression) d'un bulletin
du mois est marqué « à refaire » : le bandeau le nomme (audit du 04/10).
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import supabase
from app.modules.exports.application.a_refaire import ids_des_exports_a_refaire
from app.modules.exports.application.scheduled_exports import EXPORT_TYPE_LABELS

logger = logging.getLogger(__name__)


def exports_du_mois(company_id: str, year: int, month: int) -> list[dict[str, Any]]:
    """Un export par type, le plus récent, du plus ancien au plus récent ; `a_refaire`
    quand un bulletin du mois a changé depuis."""
    try:
        r = (
            supabase.table("exports_history")
            .select("id, export_type, period, status, generated_at")
            .match(
                {
                    "company_id": str(company_id),
                    "period": f"{int(year):04d}-{int(month):02d}",
                    "status": "generated",
                }
            )
            .execute()
        )
        lignes = r.data or []
        a_refaire = ids_des_exports_a_refaire(str(company_id), lignes) if lignes else set()
    except Exception:  # noqa: BLE001 — une aide à l'écran, jamais une erreur de lecture
        logger.warning("Exports du mois illisibles", exc_info=True)
        return []
    derniers: dict[str, dict[str, Any]] = {}
    for ligne in lignes:
        type_, date = str(ligne.get("export_type") or ""), str(ligne.get("generated_at") or "")
        if type_ and date > str(derniers.get(type_, {}).get("generated_at") or ""):
            derniers[type_] = ligne
    return [
        {
            "type": type_,
            "libelle": EXPORT_TYPE_LABELS.get(type_, type_),
            "date": str(ligne.get("generated_at") or ""),
            "a_refaire": str(ligne.get("id")) in a_refaire,
        }
        for type_, ligne in sorted(
            derniers.items(), key=lambda couple: str(couple[1].get("generated_at") or "")
        )
    ]
