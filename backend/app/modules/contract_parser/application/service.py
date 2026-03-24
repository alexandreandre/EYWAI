"""
Orchestration du module contract_parser.

Délègue l'extraction PDF à l'infrastructure (PdfTextExtractor).
Les commandes utilisent aussi ExtractionLLMProvider pour l'appel au LLM.
"""
from __future__ import annotations

from typing import Tuple

from app.modules.contract_parser.infrastructure.providers import pdf_text_extractor


def extract_text_from_pdf(file_content: bytes) -> Tuple[str, str]:
    """
    Extrait le texte d'un PDF (délégation à l'infrastructure).
    Retourne (texte_extrait, méthode_utilisée).
    """
    return pdf_text_extractor.extract_text(file_content)
