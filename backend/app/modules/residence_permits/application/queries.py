"""
Cas d'usage en lecture du module residence_permits.

Logique applicative déplacée depuis api/routers/residence_permits (liste titres de séjour).
Pas d'accès DB direct : list reader + calculator + enrichissement + mapping vers schéma réponse.
"""
from __future__ import annotations

from typing import List

from app.modules.residence_permits.application.service import enrich_row_with_residence_permit_status
from app.modules.residence_permits.infrastructure.mappers import enriched_row_to_list_item
from app.modules.residence_permits.infrastructure.providers import get_residence_permit_status_calculator
from app.modules.residence_permits.infrastructure.repository import ResidencePermitListRepository
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem

_repo = ResidencePermitListRepository()


def get_residence_permits_list(company_id: str) -> List[ResidencePermitListItem]:
    """
    Liste des salariés soumis au titre de séjour pour l'entreprise.
    Comportement identique à l’ancien router : filtre is_subject_to_residence_permit=True,
    employment_status in ('actif','en_sortie'), tri last_name, enrichissement par calcul de statut.
    """
    rows = _repo.get_employees_subject_for_company(company_id)
    calculator = get_residence_permit_status_calculator()
    result: List[ResidencePermitListItem] = []
    for row in rows:
        enriched = enrich_row_with_residence_permit_status(row, calculator)
        result.append(enriched_row_to_list_item(enriched))
    return result
