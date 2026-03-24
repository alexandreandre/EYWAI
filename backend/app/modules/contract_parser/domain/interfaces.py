"""
Ports (interfaces) du domaine contract_parser.

Implémentations dans infrastructure/. Aucune dépendance FastAPI ni détail technique ici.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class IPdfTextExtractor(ABC):
    """
    Extraction de texte depuis un PDF (bytes).
    Stratégie : pdfplumber → PyPDF2 → OCR selon disponibilité et contenu.
    """

    @abstractmethod
    def extract_text(self, file_content: bytes) -> Tuple[str, str]:
        """
        Extrait le texte d'un PDF.

        Returns:
            (texte_extrait, méthode_utilisée) ex. ("...", "pdfplumber") ou ("...", "OCR (Tesseract)")
        """
        ...


class IExtractionLLM(ABC):
    """
    Appel au LLM (ex. OpenAI) pour extraire des données structurées depuis un texte.
    Les prompts (contrat, RIB, questionnaire) sont gérés par l'implémentation.
    """

    @abstractmethod
    def extract_contract(self, extracted_text: str) -> Dict[str, Any]:
        """
        Retourne un dict avec clés : extracted_data, confidence, warnings.
        """
        ...

    @abstractmethod
    def extract_rib(self, extracted_text: str) -> Dict[str, Any]:
        """Même structure : extracted_data, confidence, warnings."""
        ...

    @abstractmethod
    def extract_questionnaire(self, extracted_text: str) -> Dict[str, Any]:
        """Même structure : extracted_data, confidence, warnings."""
        ...
