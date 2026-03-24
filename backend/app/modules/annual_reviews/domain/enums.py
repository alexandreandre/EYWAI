"""
Énumérations du domaine annual_reviews.
"""
from enum import Enum


class AnnualReviewStatusEnum(str, Enum):
    """Statuts d'un entretien annuel (aligné schémas)."""

    PLANIFIE = "planifie"
    EN_ATTENTE_ACCEPTATION = "en_attente_acceptation"
    ACCEPTE = "accepte"
    REFUSE = "refuse"
    REALISE = "realise"
    CLOTURE = "cloture"
