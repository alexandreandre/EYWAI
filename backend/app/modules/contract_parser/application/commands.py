"""
Commandes (cas d'usage) du module contract_parser.

Orchestration : extraction texte PDF via infrastructure, puis LLM via infrastructure.
Comportement strictement identique à l'ancien router.
"""

from __future__ import annotations

from app.modules.contract_parser.application.dto import ExtractionResultDto
from app.modules.contract_parser.infrastructure.providers import (
    extraction_llm_provider,
    pdf_text_extractor,
)


def extract_contract_from_pdf(file_content: bytes) -> ExtractionResultDto:
    """
    Extrait les données d'un contrat de travail depuis un PDF.
    Comportement identique à POST /api/contract-parser/extract-from-pdf.
    """
    extracted_text, method = pdf_text_extractor.extract_text(file_content)
    print(f"INFO: Texte extrait avec succès ({method})")
    print(f"INFO: Longueur du texte : {len(extracted_text)} caractères")
    parsed = extraction_llm_provider.extract_contract(extracted_text)
    print(
        f"INFO: Extraction réussie. Nombre de champs extraits : {len(parsed.get('extracted_data', {}))}"
    )
    return ExtractionResultDto(
        extracted_data=parsed["extracted_data"],
        confidence=parsed["confidence"],
        warnings=parsed.get("warnings", []),
    )


def extract_rib_from_pdf(file_content: bytes) -> ExtractionResultDto:
    """
    Extrait les données bancaires (RIB) depuis un PDF.
    Comportement identique à POST /api/contract-parser/extract-rib-from-pdf.
    """
    extracted_text, method = pdf_text_extractor.extract_text(file_content)
    print(f"INFO: Texte du RIB extrait avec succès ({method})")
    print(f"INFO: Longueur du texte : {len(extracted_text)} caractères")
    parsed = extraction_llm_provider.extract_rib(extracted_text)
    print(
        f"INFO: Extraction du RIB réussie. Nombre de champs extraits : {len(parsed.get('extracted_data', {}))}"
    )
    return ExtractionResultDto(
        extracted_data=parsed["extracted_data"],
        confidence=parsed["confidence"],
        warnings=parsed.get("warnings", []),
    )


def extract_questionnaire_from_pdf(file_content: bytes) -> ExtractionResultDto:
    """
    Extrait les données d'un questionnaire d'embauche depuis un PDF.
    Comportement identique à POST /api/contract-parser/extract-questionnaire-from-pdf.
    """
    extracted_text, method = pdf_text_extractor.extract_text(file_content)
    print(f"INFO: Texte du questionnaire extrait avec succès ({method})")
    print(f"INFO: Longueur du texte : {len(extracted_text)} caractères")
    parsed = extraction_llm_provider.extract_questionnaire(extracted_text)
    print(
        f"INFO: Extraction du questionnaire réussie. Nombre de champs extraits : {len(parsed.get('extracted_data', {}))}"
    )
    return ExtractionResultDto(
        extracted_data=parsed["extracted_data"],
        confidence=parsed["confidence"],
        warnings=parsed.get("warnings", []),
    )
