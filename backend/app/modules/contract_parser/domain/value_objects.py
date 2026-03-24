"""
Value objects du domaine contract_parser.

Résultat d'extraction (données + confiance + avertissements).
"""
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True)
class ExtractionResult:
    """
    Résultat d'une extraction (contrat, RIB ou questionnaire).
    Utilisé en application/domain ; mappé vers les schémas HTTP en api.
    """
    extracted_data: Dict[str, Any]
    confidence: str
    warnings: List[str]
