"""
DTOs applicatifs du module contract_parser.

Représentation interne du résultat d'extraction (contrat, RIB, questionnaire).
Même structure que les schémas HTTP pour mapping direct.
"""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class ExtractionResultDto:
    """Résultat d'extraction à retourner par les commandes (contrat, RIB, questionnaire)."""

    extracted_data: Dict[str, Any]
    confidence: str
    warnings: List[str]
