"""Prévenir le salarié le jour où son bulletin lui est remis (D5).

Un bulletin validé avant sa date de mise à disposition n'est pas notifié à la
validation (comparison_service) : cette tâche, lancée chaque jour par
`scripts/notifier_bulletins_remis.py`, le fait ce jour-là.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from app.core.database import supabase
from app.modules.payslips.application.commands import _notify_payslip_available
from app.modules.payslips.application.comparison_service import (
    _persist_salarie_notifie_le,
)
from app.modules.payslips.domain.mise_a_disposition import a_notifier
from app.modules.payslips.infrastructure.mise_a_disposition_queries import (
    jour_de_la_societe,
)
from app.shared.domain.temps_local import aujourd_hui_local

logger = logging.getLogger(__name__)

#: Une remise tombe au plus deux mois après la validation (validé le 1er,
#: remis le 28 du mois suivant).
_VALIDES_DEPUIS_JOURS = 62


def notifier_bulletins_remis(company_id: str, *, aujourd_hui: date | None = None) -> dict[str, int]:
    """Notifie les bulletins de la société remis cette semaine, une fois chacun."""
    jour = aujourd_hui or aujourd_hui_local()
    r = (
        supabase.table("payslips")
        .select("id, employee_id, company_id, year, month, status, validated_at, payslip_data")
        .eq("company_id", company_id)
        .eq("status", "valide")
        .gte("validated_at", (jour - timedelta(days=_VALIDES_DEPUIS_JOURS)).isoformat())
        .execute()
    )
    bilan = {"notifies": 0, "echecs": 0}
    for bulletin in a_notifier(r.data or [], jour=jour_de_la_societe(company_id), aujourd_hui=jour):
        donnees = bulletin.get("payslip_data")
        donnees = dict(donnees) if isinstance(donnees, dict) else {}
        if _notify_payslip_available(
            str(bulletin["employee_id"]), company_id, int(bulletin["year"]), int(bulletin["month"])
        ):
            _persist_salarie_notifie_le(str(bulletin["id"]), donnees)
            bilan["notifies"] += 1
        else:
            bilan["echecs"] += 1
    return bilan
