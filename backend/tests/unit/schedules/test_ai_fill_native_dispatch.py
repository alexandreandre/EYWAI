# backend/tests/unit/schedules/test_ai_fill_native_dispatch.py
"""Le mode TIMESHEET_EXTRACT_MODE=native route vers l'extracteur natif sans OCR."""

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _canned_hybrid_result():
    from app.modules.schedules.application.parsers.cegid_weekly import (
        CegidDayEntry,
        CegidEmployeeBlock,
        CegidParseResult,
    )
    from app.modules.schedules.application.timesheet_hybrid_extract import (
        HybridExtractResult,
    )
    from app.modules.schedules.application.timesheet_page_merge import (
        MergedExtractionResult,
    )

    block = CegidEmployeeBlock(
        matricule="001",
        raw_name="Test Emp",
        days=[CegidDayEntry(jour=2, month=6, year=2026, heures=7.0)],
        week_days=[],
        weekly_total_hours=None,
        days_expected_count=1,
        days_parsed_count=1,
        parse_warnings=[],
    )
    return HybridExtractResult(
        parse_result=CegidParseResult(
            format_detected=True, confidence=0.9, employees=[block]
        ),
        full_ocr_text="",
        extraction_method="native_pdf",
        pages_total=1,
        pages_processed=1,
        truncated=False,
        merged=MergedExtractionResult(employees=[], confidence=0.9),
    )


def test_native_mode_calls_native_extractor_not_ocr(monkeypatch):
    from app.modules.schedules.application import ai_fill

    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "native")

    with (
        patch.object(
            ai_fill, "_native_extractor", return_value=_canned_hybrid_result()
        ) as mock_native,
        patch(
            "app.modules.schedules.application.ai_fill.extract_document_text"
        ) as mock_ocr_prescan,
    ):
        response = ai_fill.extract_timesheet(
            year=2026,
            month=6,
            file_content=b"%PDF-1.4 fake",
            filename="releve.pdf",
            roster=[],
            skip_audit=True,
        )

    mock_native.assert_called_once()
    mock_ocr_prescan.assert_not_called()
    assert response.extraction_method == "native_pdf"
    assert response.extraction_mode == "native"
