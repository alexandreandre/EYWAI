"""
DTOs applicatifs annual_reviews.

Les schémas Pydantic (AnnualReviewCreate, AnnualReviewUpdate) servent de DTOs
pour les commandes. DTOs dédiés ci-dessous pour résultats ou données internes.
"""

from dataclasses import dataclass


@dataclass
class AnnualReviewPdfResult:
    """Résultat de la génération PDF (bytes + nom de fichier)."""

    content: bytes
    filename: str


# Création / mise à jour : utilisation directe des schémas
# AnnualReviewCreate -> commands.create_annual_review(data.model_dump())
# AnnualReviewUpdate -> commands.update_annual_review(..., data.model_dump(exclude_unset=True))

__all__ = ["AnnualReviewPdfResult"]
