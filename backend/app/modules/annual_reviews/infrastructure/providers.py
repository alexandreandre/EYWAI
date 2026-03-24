"""
Providers annual_reviews : PDF generator.

Implémentation autonome (app/modules/annual_reviews/infrastructure/pdf_generator).
Plus de dépendance à services/*.
"""
from typing import Any, Dict

from app.modules.annual_reviews.domain.interfaces import IAnnualReviewPdfGenerator
from app.modules.annual_reviews.infrastructure.pdf_generator import generate_annual_review_pdf


class AnnualReviewPdfGenerator(IAnnualReviewPdfGenerator):
    """Génère le PDF de fiche d'entretien (via infrastructure/pdf_generator)."""

    def generate(
        self,
        review_data: Dict[str, Any],
        employee_data: Dict[str, Any],
        company_data: Dict[str, Any],
    ) -> bytes:
        return generate_annual_review_pdf(review_data, employee_data, company_data)


def get_annual_review_pdf_generator() -> IAnnualReviewPdfGenerator:
    """Retourne le générateur PDF du module (autonome)."""
    return AnnualReviewPdfGenerator()
