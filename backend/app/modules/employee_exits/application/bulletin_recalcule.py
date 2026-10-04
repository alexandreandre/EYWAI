"""Un bulletin recalculé après les documents de sortie : ceux qui en reprennent
les montants sont « à revoir ».

Le solde de tout compte reprend le bulletin du mois de sortie, l'attestation
employeur les salaires des mois qui la précèdent ; tous deux sont figés en PDF
à leur génération. Corriger un de ces bulletins ensuite les laissait faux sans
rien dire. La note posée sur le départ suit le mécanisme déjà lu par l'écran du
départ pour un changement de type ou de date (`generated_documents_to_review`) :
un document généré avant la note est signalé, un document régénéré après ne
l'est plus.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.modules.employee_exits.infrastructure.repository import (
    EmployeeExitRepository,
    ExitDocumentRepository,
)

logger = get_logger(__name__)

CLE_NOTE = "bulletin_recalcule"
#: L'attestation employeur peut reprendre jusqu'à 24 mois de salaires.
MOIS_DE_L_ATTESTATION = 24


def _rang(annee: int, mois: int) -> int:
    return annee * 12 + mois


def types_tires_du_bulletin(last_working_day: Any, year: int, month: int) -> list[str]:
    """Les documents de sortie dont les montants viennent du bulletin de ce mois."""
    try:
        fin = date.fromisoformat(str(last_working_day)[:10])
    except (TypeError, ValueError):
        return []
    sortie, bulletin = _rang(fin.year, fin.month), _rang(year, month)
    types: list[str] = []
    if sortie - MOIS_DE_L_ATTESTATION <= bulletin <= sortie:
        types.append("attestation_pole_emploi")
    if bulletin == sortie:
        types.append("solde_tout_compte")
    return types


def signaler_bulletin_recalcule(
    employee_id: str,
    company_id: str,
    year: int,
    month: int,
    *,
    exits: EmployeeExitRepository | None = None,
    documents: ExitDocumentRepository | None = None,
    maintenant: datetime | None = None,
) -> None:
    """Pose la note « bulletin recalculé » sur les départs dont un document généré
    reprend ce bulletin."""
    exits = exits or EmployeeExitRepository()
    documents = documents or ExitDocumentRepository()
    instant = (maintenant or datetime.now(timezone.utc)).isoformat()
    for sortie in exits.list(company_id, employee_id=employee_id):
        if str(sortie.get("status") or "") == "annulee":
            continue
        concernes = types_tires_du_bulletin(sortie.get("last_working_day"), year, month)
        if not concernes:
            continue
        generes = sorted(
            {
                str(doc.get("document_type"))
                for doc in documents.list_by_exit(str(sortie["id"]), company_id)
                if doc.get("document_category") == "generated"
                and doc.get("document_type") in concernes
            }
        )
        if not generes:
            continue
        notes = sortie.get("exit_notes")
        notes = dict(notes) if isinstance(notes, dict) else {}
        notes[CLE_NOTE] = {
            "timestamp": instant,
            "periode": f"{month:02d}/{year}",
            "generated_documents_to_review": generes,
        }
        exits.update(str(sortie["id"]), company_id, {"exit_notes": notes})
