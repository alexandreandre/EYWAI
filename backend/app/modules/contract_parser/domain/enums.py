"""
Énumérations du domaine contract_parser.

Type de document à extraire (contrat, RIB, questionnaire).
"""

from enum import Enum


class ExtractionType(str, Enum):
    """Type de document PDF à traiter pour l'extraction."""

    CONTRACT = "contract"
    RIB = "rib"
    QUESTIONNAIRE = "questionnaire"
