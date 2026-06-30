"""Tests canal texte hybride ignoré si OCR non fiable."""

from unittest.mock import MagicMock, patch

from app.modules.schedules.application.timesheet_hybrid_extract import (
    _extract_single_page_hybrid,
)
from app.shared.infrastructure.documents.text_extraction import RenderedPage


@patch("app.modules.schedules.application.timesheet_hybrid_extract.is_llm_configured", return_value=True)
@patch("app.modules.schedules.application.timesheet_hybrid_extract.timesheet_hybrid_adaptive", return_value=True)
@patch("app.modules.schedules.application.timesheet_hybrid_extract.is_ocr_text_reliable", return_value=False)
@patch("app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json_from_image")
@patch("app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json")
def test_skips_text_llm_when_ocr_unreliable(
    mock_text_llm,
    mock_vision,
    _mock_reliable,
    _mock_adaptive,
    _mock_llm,
):
    mock_vision.return_value = MagicMock(
        data={"employees": [], "page_period_hint": None, "confidence": 0.8, "warnings": []},
        tokens_used=10,
    )
    page = RenderedPage(
        page_index=1,
        png_bytes=b"jpeg",
        ocr_text="AH 9 lANOHINV garbage",
        vision_mime_type="image/jpeg",
    )
    _extract_single_page_hybrid(
        page,
        year=2026,
        month=5,
        pages_total=1,
        matricule_hint="",
    )
    mock_vision.assert_called_once()
    mock_text_llm.assert_not_called()
