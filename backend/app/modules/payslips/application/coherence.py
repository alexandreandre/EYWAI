"""Lecture du mois précédent pour dire si un bulletin est à régénérer."""

from __future__ import annotations

import logging
from typing import Any

from app.core.database import supabase
from app.modules.payroll.domain.empreinte_entrees import (  # noqa: F401 — réexporté
    message_mois_d_avant_a_recalculer,
)
from app.modules.payslips.domain.coherence import (
    MESSAGE_A_REGENERER,
    a_regenerer,
    cumul_brut,
)

logger = logging.getLogger(__name__)


def cumul_brut_du_mois_precedent(employee_id: str, year: int, month: int) -> float | None:
    """Le brut cumulé à la fin du mois précédent, dans la même année ; None sinon."""
    if int(month) <= 1:
        return None
    try:
        r = (
            supabase.table("payslips")
            .select("cumuls:payslip_data->cumuls")
            .match({"employee_id": str(employee_id), "year": int(year), "month": int(month) - 1})
            .maybe_single()
            .execute()
        )
    except Exception:  # noqa: BLE001 — le signal est une aide, pas une garde de lecture
        logger.warning("Cumuls du mois précédent illisibles", exc_info=True)
        return None
    if not r or not r.data:
        return None
    return cumul_brut({"cumuls": r.data.get("cumuls")})


def signal_a_regenerer(
    bulletin: dict[str, Any],
    cumuls_precedents_changes: bool | None = None,
    cascade_depuis: tuple[int, int] | None = None,
) -> str | None:
    """La phrase « à régénérer » quand le mois d'avant a changé depuis le calcul.

    Rien pour un bulletin repris : il n'est pas recalculable, sa chaîne fait foi.
    Un mois plus ancien de la chaîne recalculé depuis (`cascade_depuis`) se dit
    en le nommant : c'est lui qu'il faut recalculer d'abord. Sinon l'empreinte
    des cumuls du mois d'avant (`cumuls_precedents_changes`, posée à la
    génération) décide quand elle est connue : elle voit tous les cumuls, pas
    le seul brut, et sait qu'un premier mois de contrat n'en dépend pas. Sans
    elle (bulletin calculé avant), on contrôle le brut cumulé.
    """
    if str(bulletin.get("origine") or "calcule") == "importe":
        return None
    try:
        ce_mois = (int(bulletin["year"]), int(bulletin["month"]))
    except (KeyError, TypeError, ValueError):
        ce_mois = None
    if cascade_depuis is not None and cascade_depuis != ce_mois:
        return message_mois_d_avant_a_recalculer(*cascade_depuis)
    if cumuls_precedents_changes is not None:
        return MESSAGE_A_REGENERER if cumuls_precedents_changes else None
    try:
        precedent = cumul_brut_du_mois_precedent(
            bulletin["employee_id"], bulletin["year"], bulletin["month"]
        )
    except (KeyError, TypeError, ValueError):
        return None
    return a_regenerer(bulletin.get("payslip_data"), precedent)
