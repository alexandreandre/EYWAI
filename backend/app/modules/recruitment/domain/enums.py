# app/modules/recruitment/domain/enums.py
"""Enums du domaine recruitment — alignés sur le comportement legacy."""
from enum import StrEnum


class StageType(StrEnum):
    """Type d'étape du pipeline (standard, rejected, hired)."""
    STANDARD = "standard"
    REJECTED = "rejected"
    HIRED = "hired"


class OpinionRating(StrEnum):
    """Avis sur un candidat."""
    FAVORABLE = "favorable"
    DEFAVORABLE = "defavorable"
