# app/modules/recruitment/infrastructure/providers.py
"""
Providers recruitment : settings, constantes (motifs de refus, pipeline par défaut).
Placeholders / wrappers pour migration progressive depuis services/recruitment_service.
"""

from typing import List

# Aligné sur services/recruitment_service.REJECTION_REASONS — à garder identique
REJECTION_REASONS: List[str] = [
    "Profil non adapté",
    "Manque d'expérience",
    "Prétentions salariales",
    "Candidat a décliné",
    "Poste pourvu",
    "Autre",
]

# Aligné sur services/recruitment_service.DEFAULT_PIPELINE_STAGES
DEFAULT_PIPELINE_STAGES: List[dict] = [
    {
        "name": "Premier appel",
        "position": 0,
        "stage_type": "standard",
        "is_final": False,
    },
    {
        "name": "Entretien RH",
        "position": 1,
        "stage_type": "standard",
        "is_final": False,
    },
    {"name": "Entretien 1", "position": 2, "stage_type": "standard", "is_final": False},
    {"name": "Entretien 2", "position": 3, "stage_type": "standard", "is_final": False},
    {
        "name": "Offre envoyée",
        "position": 4,
        "stage_type": "standard",
        "is_final": False,
    },
    {"name": "Refusé", "position": 5, "stage_type": "rejected", "is_final": True},
    {"name": "Recruté", "position": 6, "stage_type": "hired", "is_final": True},
]


def get_recruitment_setting_placeholder(company_id: str) -> bool:
    """
    Wrapper placeholder : lors de la migration, implémenter IRecruitmentSettingsReader
    (lecture table company_settings ou équivalent). Comportement actuel legacy : toujours True.
    """
    return True
