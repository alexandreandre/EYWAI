"""Tests unitaires — extraction OCR PDF (relevés pointages)."""

from unittest.mock import MagicMock, patch

from app.shared.infrastructure.documents.text_extraction import (
    _extract_pdf_ocr,
    extract_document_text,
)


class TestExtractPdfOcr:
    def test_processes_all_pages_when_under_cap(self, monkeypatch):
        monkeypatch.setenv("TIMESHEET_OCR_MAX_PAGES", "50")
        fake_img = MagicMock()
        with patch(
            "app.shared.infrastructure.documents.text_extraction.convert_from_bytes",
            return_value=[fake_img],
        ) as mock_convert, patch(
            "app.shared.infrastructure.documents.text_extraction._ocr_image_adaptive",
            return_value=("page text", 6),
        ) as mock_adaptive, patch(
            "app.shared.infrastructure.documents.text_extraction._ocr_image_with_psm",
            return_value="page text",
        ) as mock_psm:
            text, psm, processed, total = _extract_pdf_ocr(
                b"pdf", total_pages=12
            )

        assert processed == 12
        assert total == 12
        assert mock_convert.call_count == 12
        mock_adaptive.assert_called_once()
        assert mock_psm.call_count == 11
        assert "page text" in text
        assert psm == 6

    def test_truncates_at_max_pages_cap(self, monkeypatch):
        monkeypatch.setenv("TIMESHEET_OCR_MAX_PAGES", "50")
        fake_img = MagicMock()
        with patch(
            "app.shared.infrastructure.documents.text_extraction.convert_from_bytes",
            return_value=[fake_img],
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._ocr_image_adaptive",
            return_value=("x", 4),
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._ocr_image_with_psm",
            return_value="x",
        ):
            _text, _psm, processed, total = _extract_pdf_ocr(
                b"pdf", total_pages=60
            )

        assert processed == 50
        assert total == 60

    def test_eight_pages_not_truncated_in_metadata(self, monkeypatch):
        monkeypatch.setenv("TIMESHEET_OCR_MAX_PAGES", "50")
        with patch(
            "app.shared.infrastructure.documents.text_extraction._pdf_page_count",
            return_value=8,
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._extract_pdf_native",
            return_value="",
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._extract_pdf_ocr",
            return_value=("ocr ok " * 10, 6, 8, 8),
        ):
            _text, method, meta = extract_document_text(b"pdf", "releve.pdf")

        assert method == "OCR PDF (Tesseract)"
        assert meta.ocr_pages_processed == 8
        assert meta.ocr_pages_total == 8
        assert meta.truncated is False
        assert not meta.warnings

    def test_partial_ocr_sets_truncation_warning(self, monkeypatch):
        monkeypatch.setenv("TIMESHEET_OCR_MAX_PAGES", "50")
        with patch(
            "app.shared.infrastructure.documents.text_extraction._pdf_page_count",
            return_value=20,
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._extract_pdf_native",
            return_value="",
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._extract_pdf_ocr",
            return_value=("ocr ok " * 10, 6, 15, 20),
        ):
            _text, _method, meta = extract_document_text(b"pdf", "releve.pdf")

        assert meta.truncated is True
        assert any("15" in w and "20" in w for w in meta.warnings)


class TestExtractDocumentTextNative:
    def test_native_pdf_sets_page_counts(self):
        with patch(
            "app.shared.infrastructure.documents.text_extraction._pdf_page_count",
            return_value=14,
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._extract_pdf_native",
            return_value="x" * 100,
        ), patch(
            "app.shared.infrastructure.documents.text_extraction._should_force_ocr",
            return_value=False,
        ):
            _text, method, meta = extract_document_text(b"pdf", "releve.pdf")

        assert method == "PDF natif"
        assert meta.ocr_pages_total == 14
        assert meta.ocr_pages_processed == 14
        assert meta.truncated is False
