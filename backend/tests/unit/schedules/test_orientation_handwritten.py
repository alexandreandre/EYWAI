"""Tests auto-rotation pour feuilles manuscrites photographiées."""

from pathlib import Path

import pytest

from app.shared.infrastructure.documents.text_extraction import (
    DocumentExtractionError,
    _orientation_quality_score,
    render_document_pages,
)

COLORPLAST_PDF = (
    Path(__file__).resolve().parents[4]
    / "Config"
    / "Colorplast"
    / "Pointages"
    / "semaine 18 (5).pdf"
)


def test_orientation_score_prefers_debut_fin_over_garbage():
    garbage = "_NORHVAI_\nAH 9 lANOHINV\n" * 5
    handwritten = "S18\nLUNDI MARDI\nDEBUT FIN\nHUGO\nANTHONY\n" * 3
    assert _orientation_quality_score(handwritten) > _orientation_quality_score(garbage)


@pytest.mark.skipif(not COLORPLAST_PDF.exists(), reason="PDF Colorplast absent")
def test_colorplast_pdf_oriented_for_vision():
    content = COLORPLAST_PDF.read_bytes()
    try:
        doc = render_document_pages(content, COLORPLAST_PDF.name)
    except DocumentExtractionError as exc:
        pytest.skip(f"OCR local indisponible pour le PDF réel: {exc}")
    page = doc.pages[0]
    assert page.vision_mime_type == "image/jpeg"
    assert len(page.png_bytes) <= 8 * 1024 * 1024
    upper = (page.ocr_text or "").upper()
    assert "DEBUT" in upper or "ANTHONY" in upper or "HUGO" in upper
