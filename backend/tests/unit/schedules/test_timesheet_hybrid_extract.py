"""Tests orchestrateur hybride (LLM mocké)."""

from unittest.mock import patch

import pytest

from app.modules.schedules.application.timesheet_hybrid_extract import (
    extract_timesheet_hybrid,
)
from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult


def _page_json(name: str, mat: str, jour: int, heures: float) -> dict:
    return {
        "employees": [
            {
                "raw_name": name,
                "matricule": mat,
                "weekly_total_pdf": heures,
                "days": [{"jour": jour, "heures": heures, "type": "travail"}],
            }
        ],
        "page_period_hint": "SEMAINE 22",
        "confidence": 0.85,
        "warnings": [],
    }


@pytest.fixture
def minimal_png() -> bytes:
    from PIL import Image
    import io

    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@patch("app.modules.schedules.application.timesheet_hybrid_extract.is_llm_configured", return_value=True)
@patch("app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json_from_image")
@patch("app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json")
@patch("app.modules.schedules.application.timesheet_hybrid_extract.render_document_pages")
def test_hybrid_extract_mocks(
    mock_render,
    mock_text_llm,
    mock_vision_llm,
    _llm_ok,
    minimal_png,
):
    from app.shared.infrastructure.documents.text_extraction import (
        RenderedDocument,
        RenderedPage,
    )

    mock_render.return_value = RenderedDocument(
        pages=[
            RenderedPage(
                page_index=1,
                png_bytes=minimal_png,
                ocr_text="DUPONT Jean 42 # 7:00",
            )
        ],
        pages_total=1,
        pages_processed=1,
    )
    payload = _page_json("DUPONT Jean", "42", 25, 7.0)
    mock_vision_llm.return_value = StructuredExtractionResult(data=payload, tokens_used=50)
    mock_text_llm.return_value = StructuredExtractionResult(data=payload, tokens_used=40)

    result = extract_timesheet_hybrid(
        file_content=b"fake",
        filename="test.pdf",
        year=2026,
        month=5,
    )
    assert len(result.parse_result.employees) >= 1
    assert result.tokens_used == 90
    assert result.extraction_method == "hybrid_vision_ocr"
