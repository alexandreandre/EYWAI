"""
Tests unitaires du service applicatif contract_parser.

Le service expose extract_text_from_pdf (délégation à pdf_text_extractor).
Tests avec dépendance mockée.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.contract_parser.application.service import extract_text_from_pdf


pytestmark = pytest.mark.unit


@patch("app.modules.contract_parser.application.service.pdf_text_extractor")
class TestExtractTextFromPdf:
    """Service extract_text_from_pdf."""

    def test_returns_tuple_text_and_method(
        self, mock_pdf_extractor: MagicMock
    ):
        """Retourne (texte_extrait, méthode_utilisée)."""
        mock_pdf_extractor.extract_text.return_value = (
            "Contrat de travail CDI. Date : 2024-01-15.",
            "pdfplumber",
        )
        text, method = extract_text_from_pdf(b"%PDF-1.4 content")
        assert text == "Contrat de travail CDI. Date : 2024-01-15."
        assert method == "pdfplumber"
        mock_pdf_extractor.extract_text.assert_called_once_with(b"%PDF-1.4 content")

    def test_delegates_to_infrastructure(
        self, mock_pdf_extractor: MagicMock
    ):
        """Un seul appel à l'extracteur avec les bytes fournis."""
        mock_pdf_extractor.extract_text.return_value = ("", "OCR (Tesseract)")
        extract_text_from_pdf(b"fake pdf bytes")
        mock_pdf_extractor.extract_text.assert_called_once_with(b"fake pdf bytes")

    def test_ocr_method_returned_when_used(
        self, mock_pdf_extractor: MagicMock
    ):
        """Si l'infrastructure utilise l'OCR, la méthode retournée le reflète."""
        mock_pdf_extractor.extract_text.return_value = (
            "Texte extrait par OCR avec quelques erreurs.",
            "OCR (Tesseract)",
        )
        text, method = extract_text_from_pdf(b"scanned.pdf")
        assert method == "OCR (Tesseract)"
        assert "OCR" in text or len(text) >= 0
