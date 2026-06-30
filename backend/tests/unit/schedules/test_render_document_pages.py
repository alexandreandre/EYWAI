"""Tests render_document_pages."""

from unittest.mock import MagicMock, patch

from app.shared.infrastructure.documents.text_extraction import render_document_pages


@patch("app.shared.infrastructure.documents.text_extraction._OCR_AVAILABLE", True)
@patch("app.shared.infrastructure.documents.text_extraction._image_to_vision_bytes", return_value=(b"jpeg-bytes", "image/jpeg"))
@patch("app.shared.infrastructure.documents.text_extraction.Image")
@patch("app.shared.infrastructure.documents.text_extraction._ocr_image_adaptive")
def test_render_single_image(mock_ocr, mock_image_cls, _mock_vision):
    mock_img = MagicMock()
    mock_image_cls.open.return_value = mock_img
    mock_ocr.return_value = ("DUPONT 42", 6, mock_img, 0)

    doc = render_document_pages(b"fake-image", "scan.png")
    assert doc.pages_processed == 1
    assert doc.pages[0].ocr_text == "DUPONT 42"
    assert len(doc.pages[0].png_bytes) > 0
