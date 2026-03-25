# app/modules/recruitment/domain/rules.py
"""
Règles métier pures recruitment — sans dépendance DB ni FastAPI.
Utilisées par la couche application avant d'appeler l'infrastructure.
"""

from typing import Tuple

# Valeurs autorisées pour l'avis candidat (contract API)
VALID_OPINION_RATINGS: Tuple[str, ...] = ("favorable", "defavorable")


def require_rejection_reason_for_rejected_stage(
    stage_type: str, rejection_reason: str | None
) -> bool:
    """Si l'étape est 'rejected', un motif de refus est obligatoire."""
    if stage_type != "rejected":
        return True
    return bool(rejection_reason and rejection_reason.strip())


def can_delete_candidate(stage_position: int) -> bool:
    """Suppression autorisée seulement en début de pipeline (position 1)."""
    return stage_position <= 1


def is_valid_opinion_rating(rating: str) -> bool:
    """L'avis doit être 'favorable' ou 'defavorable'."""
    return rating in VALID_OPINION_RATINGS
