"""
Types d'entretien — source de vérité unique (backend).

Synchroniser les libellés front dans frontend/src/api/annualReviews.ts.
"""

from typing import Literal

InterviewType = Literal[
    "annual_performance",
    "professional_2ans",
    "competency_6ans",
    "annual_cadres",
    "annual_forfait_jour",
    "return_absence",
    "mid_year",
    "other",
]

INTERVIEW_TYPE_LABELS: dict[str, str] = {
    "annual_performance": "Entretien annuel",
    "professional_2ans": "Entretien professionnel (2 ans)",
    "competency_6ans": "Bilan de compétences (6 ans)",
    "annual_cadres": "Entretien annuel des cadres",
    "annual_forfait_jour": "Entretien annuel de suivi forfait jour",
    "return_absence": (
        "Entretien professionnel de reprise d'activité suite à absence longue durée"
    ),
    "mid_year": "Entretien de mi-année",
    "other": "Autre",
}

# Obligations L6315-1 (mention légale sur PDF)
L6315_INTERVIEW_TYPES = frozenset(
    {
        "professional_2ans",
        "competency_6ans",
        "return_absence",
    }
)

# Statuts autorisés pour télécharger / consulter la convocation
CONVOCATION_ALLOWED_STATUSES = frozenset(
    {
        "en_attente_acceptation",
        "accepte",
        "refuse",
        "realise",
        "cloture",
    }
)

# Statuts considérés comme « entretien couvert » pour une année donnée
ACTIVE_OR_COMPLETED_REVIEW_STATUSES = frozenset(
    {
        "planifie",
        "en_attente_acceptation",
        "accepte",
        "realise",
        "cloture",
    }
)


# Statuts d'un entretien réellement tenu : seuls ceux-ci font repartir le cycle
# (un entretien planifié puis jamais tenu ne doit pas repousser l'échéance suivante).
COMPLETED_REVIEW_STATUSES = frozenset({"realise", "cloture"})


def interview_type_label(interview_type: str | None) -> str:
    """Libellé affichable pour un code type d'entretien."""
    if not interview_type:
        return INTERVIEW_TYPE_LABELS["annual_performance"]
    return INTERVIEW_TYPE_LABELS.get(interview_type, interview_type)


__all__ = [
    "InterviewType",
    "INTERVIEW_TYPE_LABELS",
    "L6315_INTERVIEW_TYPES",
    "CONVOCATION_ALLOWED_STATUSES",
    "ACTIVE_OR_COMPLETED_REVIEW_STATUSES",
    "COMPLETED_REVIEW_STATUSES",
    "interview_type_label",
]
