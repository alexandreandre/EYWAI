"""
Queries applicatives annual_reviews.

Orchestration : repository (infrastructure) + règles métier (domain) + mappers.
Comportement strictement identique au legacy.
"""

from typing import List, Optional

from app.modules.annual_reviews.domain.interfaces import IAnnualReviewRepository
from app.modules.annual_reviews.domain.rules import validate_pdf_allowed
from app.modules.annual_reviews.infrastructure.mappers import (
    row_to_annual_review_read,
    row_to_list_item,
)
from app.modules.annual_reviews.schemas.responses import (
    AnnualReviewListItem,
    AnnualReviewRead,
)


def list_all_annual_reviews(
    company_id: str,
    repository: IAnnualReviewRepository,
    year: Optional[int] = None,
    status: Optional[str] = None,
) -> List[AnnualReviewListItem]:
    """Liste tous les entretiens de l'entreprise (vue RH avec noms employés)."""
    rows = repository.list_by_company(company_id, year=year, status=status)
    return [row_to_list_item(r) for r in rows]


def get_annual_review_by_id(
    review_id: str,
    company_id: str,
    current_user_id: str,
    is_rh: bool,
    repository: IAnnualReviewRepository,
) -> Optional[AnnualReviewRead]:
    """Récupère un entretien par id (avec vérif company + accès employé/RH)."""
    row = repository.get_by_id(review_id)
    if not row:
        return None
    if row["company_id"] != company_id:
        return None
    if not is_rh and row["employee_id"] != current_user_id:
        return None
    return row_to_annual_review_read(row)


def list_employee_annual_reviews(
    employee_id: str,
    company_id: str,
    repository: IAnnualReviewRepository,
) -> List[AnnualReviewRead]:
    """Liste les entretiens d'un employé. RH uniquement. Lève LookupError si employé hors entreprise."""
    emp_company_id = repository.get_employee_company_id(employee_id)
    if not emp_company_id or emp_company_id != company_id:
        raise LookupError("Employé non trouvé.")
    rows = repository.list_by_employee(employee_id, company_id)
    return [row_to_annual_review_read(r) for r in rows]


def get_my_annual_reviews(
    employee_id: str,
    company_id: str,
    repository: IAnnualReviewRepository,
) -> List[AnnualReviewRead]:
    """Liste les entretiens de l'utilisateur connecté."""
    rows = repository.list_by_employee(employee_id, company_id)
    return [row_to_annual_review_read(r) for r in rows]


def get_my_current_annual_review(
    employee_id: str,
    company_id: str,
    year: int,
    repository: IAnnualReviewRepository,
) -> Optional[AnnualReviewRead]:
    """Entretien de l'année courante pour l'utilisateur connecté."""
    row = repository.get_my_current(employee_id, company_id, year)
    if not row:
        return None
    return row_to_annual_review_read(row)


def get_annual_review_for_pdf(
    review_id: str,
    company_id: str,
    current_user_id: str,
    is_rh: bool,
    repository: IAnnualReviewRepository,
) -> Optional[dict]:
    """
    Récupère l'entretien pour génération PDF (avec vérif cloture).
    Retourne un dict pour usage interne (review_data). Lever ValueError si non clôturé.
    """
    row = repository.get_by_id(review_id)
    if not row:
        return None
    if row["company_id"] != company_id:
        return None
    if not is_rh and row["employee_id"] != current_user_id:
        return None
    validate_pdf_allowed(row.get("status", ""))
    return row
