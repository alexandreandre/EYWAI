"""
Tests unitaires des commandes du module contract_parser.

Chaque commande (extract_contract_from_pdf, extract_rib_from_pdf,
extract_questionnaire_from_pdf) est testée avec extracteur PDF et LLM mockés.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.contract_parser.application.commands import (
    extract_contract_from_pdf,
    extract_rib_from_pdf,
    extract_questionnaire_from_pdf,
)
from app.modules.contract_parser.application.dto import ExtractionResultDto


pytestmark = pytest.mark.unit


def _make_parsed(extracted_data=None, confidence="high", warnings=None):
    """Structure retournée par le LLM mock."""
    return {
        "extracted_data": extracted_data or {},
        "confidence": confidence,
        "warnings": warnings or [],
    }


@patch("app.modules.contract_parser.application.commands.extraction_llm_provider")
@patch("app.modules.contract_parser.application.commands.pdf_text_extractor")
class TestExtractContractFromPdf:
    """Commande extract_contract_from_pdf."""

    def test_returns_dto_with_extracted_data(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Appelle extracteur puis LLM et retourne ExtractionResultDto."""
        mock_pdf.extract_text.return_value = (
            "Contrat CDI entre X et M. Dupont. Date 2024-01-15.",
            "pdfplumber",
        )
        mock_llm.extract_contract.return_value = _make_parsed(
            extracted_data={"first_name": "Jean", "last_name": "Dupont", "hire_date": "2024-01-15"},
            confidence="high",
            warnings=[],
        )
        result = extract_contract_from_pdf(b"%PDF-1.4 fake content")
        assert isinstance(result, ExtractionResultDto)
        assert result.extracted_data["first_name"] == "Jean"
        assert result.extracted_data["last_name"] == "Dupont"
        assert result.confidence == "high"
        assert result.warnings == []
        mock_pdf.extract_text.assert_called_once_with(b"%PDF-1.4 fake content")
        mock_llm.extract_contract.assert_called_once()

    def test_passes_extracted_text_to_llm(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Le texte retourné par l'extracteur est passé au LLM."""
        extracted_text = "CONTRAT DE TRAVAIL\nDate : 01/03/2024"
        mock_pdf.extract_text.return_value = (extracted_text, "PyPDF2")
        mock_llm.extract_contract.return_value = _make_parsed(extracted_data={})
        extract_contract_from_pdf(b"pdf bytes")
        mock_llm.extract_contract.assert_called_once_with(extracted_text)

    def test_handles_llm_warnings(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Les warnings du LLM sont renvoyés dans le DTO."""
        mock_pdf.extract_text.return_value = ("texte", "pdfplumber")
        mock_llm.extract_contract.return_value = _make_parsed(
            extracted_data={"hire_date": "2024-01-01"},
            confidence="medium",
            warnings=["Date d'embauche ambiguë"],
        )
        result = extract_contract_from_pdf(b"pdf")
        assert result.warnings == ["Date d'embauche ambiguë"]
        assert result.confidence == "medium"


@patch("app.modules.contract_parser.application.commands.extraction_llm_provider")
@patch("app.modules.contract_parser.application.commands.pdf_text_extractor")
class TestExtractRibFromPdf:
    """Commande extract_rib_from_pdf."""

    def test_returns_dto_with_rib_data(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Extraction RIB : IBAN, BIC dans extracted_data."""
        mock_pdf.extract_text.return_value = (
            "IBAN FR76 1234 5678 9012 3456 7890 123\nBIC SOGEFRPP",
            "pdfplumber",
        )
        mock_llm.extract_rib.return_value = _make_parsed(
            extracted_data={
                "iban": "FR7612345678901234567890123",
                "bic": "SOGEFRPP",
                "titulaire": "Jean Dupont",
            },
            confidence="high",
            warnings=[],
        )
        result = extract_rib_from_pdf(b"rib.pdf bytes")
        assert result.extracted_data["iban"] == "FR7612345678901234567890123"
        assert result.extracted_data["bic"] == "SOGEFRPP"
        mock_llm.extract_rib.assert_called_once()

    def test_passes_extracted_text_to_llm(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Le texte du RIB est passé à extract_rib."""
        rib_text = "Relevé d'identité bancaire\nIBAN FR76..."
        mock_pdf.extract_text.return_value = (rib_text, "OCR (Tesseract)")
        mock_llm.extract_rib.return_value = _make_parsed(extracted_data={})
        extract_rib_from_pdf(b"bytes")
        mock_llm.extract_rib.assert_called_once_with(rib_text)


@patch("app.modules.contract_parser.application.commands.extraction_llm_provider")
@patch("app.modules.contract_parser.application.commands.pdf_text_extractor")
class TestExtractQuestionnaireFromPdf:
    """Commande extract_questionnaire_from_pdf."""

    def test_returns_dto_with_questionnaire_data(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Extraction questionnaire : champs candidat + poste."""
        mock_pdf.extract_text.return_value = (
            "Questionnaire d'embauche. Nom : Martin. Poste : Développeur.",
            "pdfplumber",
        )
        mock_llm.extract_questionnaire.return_value = _make_parsed(
            extracted_data={
                "first_name": "Marie",
                "last_name": "Martin",
                "job_title": "Développeur",
                "contract_type": "CDI",
            },
            confidence="medium",
            warnings=["Salaire non renseigné"],
        )
        result = extract_questionnaire_from_pdf(b"questionnaire.pdf bytes")
        assert result.extracted_data["first_name"] == "Marie"
        assert result.extracted_data["job_title"] == "Développeur"
        assert result.warnings == ["Salaire non renseigné"]
        mock_llm.extract_questionnaire.assert_called_once()

    def test_passes_extracted_text_to_llm(
        self, mock_pdf: MagicMock, mock_llm: MagicMock
    ):
        """Le texte du questionnaire est passé à extract_questionnaire."""
        q_text = "Questionnaire\nPrénom : ..."
        mock_pdf.extract_text.return_value = (q_text, "pdfplumber")
        mock_llm.extract_questionnaire.return_value = _make_parsed(extracted_data={})
        extract_questionnaire_from_pdf(b"bytes")
        mock_llm.extract_questionnaire.assert_called_once_with(q_text)
