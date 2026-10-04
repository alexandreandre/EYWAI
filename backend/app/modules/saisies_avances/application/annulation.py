"""Défaire ce qu'un bulletin a retenu sur les avances et acomptes : l'avance se rouvre.

Le bulletin retient l'avance (ligne `salary_advance_repayments`), baisse son
reste à rembourser et, si elle n'était qu'approuvée, la marque versée.
Recalculer sans rien rendre perdait l'avance (plus rien à rembourser) ; la
défaire rend le reste et le statut que ses versements lui donnent, puis le
recalcul retient une fois.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

from app.modules.saisies_avances.infrastructure.enrichment import (
    remboursements_d_avance_du_bulletin,
    supprimer_remboursement_d_avance,
)
from app.modules.saisies_avances.infrastructure.repository import (
    advance_payment_repository,
    advance_repository,
)

logger = logging.getLogger(__name__)


def _centimes(valeur: Any) -> Decimal:
    return Decimal(str(valeur or 0)).quantize(Decimal("0.01"))


def defaire_remboursements_du_bulletin(payslip_id: str) -> int:
    """Rend à chaque avance ce que le bulletin en a retenu. Rend le nombre de
    remboursements défaits ; rien à défaire, 0."""
    lignes = remboursements_d_avance_du_bulletin(payslip_id)
    for ligne in lignes:
        advance_id = str(ligne["advance_id"])
        avance = advance_repository.get_by_id(advance_id)
        if avance:
            reste = _centimes(avance.get("remaining_amount")) + _centimes(ligne.get("repayment_amount"))
            maj: dict[str, Any] = {"remaining_amount": float(reste)}
            # Même règle que l'enregistrement d'un versement : versée si les
            # versements couvrent le montant approuvé, approuvée sinon.
            verse = advance_payment_repository.get_total_paid_by_advance_id(advance_id)
            if verse > 0:
                approuve = _centimes(avance.get("approved_amount"))
                maj["status"] = "paid" if verse >= approuve else "approved"
            advance_repository.update(advance_id, maj)
        supprimer_remboursement_d_avance(str(ligne["id"]))
    if lignes:
        logger.info(
            "[effets] Bulletin %s : %d remboursement(s) d'avance défait(s).", payslip_id, len(lignes)
        )
    return len(lignes)
