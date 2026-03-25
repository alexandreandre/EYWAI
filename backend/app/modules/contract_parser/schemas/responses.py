"""
Schémas de réponse HTTP du module contract_parser.

Définitions canoniques. Le legacy api/routers/contract_parser.py les importe d'ici.
"""

from typing import Any, Dict, List

from pydantic import BaseModel


class ContractExtractionResponse(BaseModel):
    """Réponse de l'extraction de contrat"""

    extracted_data: Dict[str, Any]
    confidence: str
    warnings: List[str]


class RIBExtractionResponse(BaseModel):
    """Réponse de l'extraction de RIB"""

    extracted_data: Dict[str, Any]
    confidence: str
    warnings: List[str]


class QuestionnaireExtractionResponse(BaseModel):
    """Réponse de l'extraction de questionnaire d'embauche"""

    extracted_data: Dict[str, Any]
    confidence: str
    warnings: List[str]
