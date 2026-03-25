"""
Service applicatif annual_reviews (orchestration).

Expose le repository et le générateur PDF ; orchestre la génération PDF
(review + employee + company -> bytes + filename). Comportement identique au legacy.
"""

from __future__ import annotations

from typing import Optional, Tuple

from app.modules.annual_reviews.domain.interfaces import (
    IAnnualReviewPdfGenerator,
    IAnnualReviewRepository,
)
from app.modules.annual_reviews.infrastructure.repository import (
    annual_review_repository,
)
from app.modules.annual_reviews.infrastructure.providers import (
    get_annual_review_pdf_generator,
)

from . import commands, queries


def get_repository() -> IAnnualReviewRepository:
    """Retourne le repository (instance Supabase)."""
    return annual_review_repository


def get_pdf_generator() -> IAnnualReviewPdfGenerator:
    """Retourne le générateur PDF (wrapper legacy)."""
    return get_annual_review_pdf_generator()


def generate_annual_review_pdf(
    review_id: str,
    company_id: str,
    current_user_id: str,
    is_rh: bool,
    repository: Optional[IAnnualReviewRepository] = None,
    pdf_generator: Optional[IAnnualReviewPdfGenerator] = None,
) -> Tuple[bytes, str]:
    """
    Génère le PDF d'un entretien clôturé.
    Retourne (pdf_bytes, filename). Lève ValueError si non clôturé ou non trouvé.
    """
    repo = repository or get_repository()
    gen = pdf_generator or get_pdf_generator()

    review_data = queries.get_annual_review_for_pdf(
        review_id, company_id, current_user_id, is_rh, repository=repo
    )
    if not review_data:
        raise LookupError("Entretien non trouvé.")

    employee_id = review_data.get("employee_id")
    employee_data = repo.get_employee_by_id(employee_id) if employee_id else {}
    if not employee_data:
        raise LookupError("Employé non trouvé.")

    company_data = repo.get_company_by_id(company_id) or {}

    pdf_bytes = gen.generate(review_data, employee_data, company_data)
    employee_name = f"{employee_data.get('first_name', '')}_{employee_data.get('last_name', '')}".strip().replace(
        " ", "_"
    )
    filename = f"entretien_{employee_name}_{review_data.get('year', '')}.pdf"
    return pdf_bytes, filename


__all__ = [
    "commands",
    "queries",
    "get_repository",
    "get_pdf_generator",
    "generate_annual_review_pdf",
]
