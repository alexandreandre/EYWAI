"""Schéma de lot natif et wrapper texte de couche PDF."""

import pytest

pytestmark = pytest.mark.unit


def test_batch_schema_wraps_page_schema_with_page_index():
    from app.modules.schedules.application.timesheet_page_schema import (
        BATCH_EXTRACTION_JSON_SCHEMA,
        PAGE_EXTRACTION_JSON_SCHEMA,
    )

    items = BATCH_EXTRACTION_JSON_SCHEMA["properties"]["pages"]["items"]
    assert "page_index" in items["properties"]
    assert "page_index" in items["required"]
    for key in PAGE_EXTRACTION_JSON_SCHEMA["properties"]:
        assert key in items["properties"]
    assert BATCH_EXTRACTION_JSON_SCHEMA["required"] == ["pages"]


def test_batch_prompt_mentions_page_range():
    from app.modules.schedules.application.timesheet_page_schema import (
        build_batch_user_prompt_native,
    )

    prompt = build_batch_user_prompt_native(
        page_start=3, page_end=4, pages_total=9, matricule_hint="Matricules GTA connus : 007."
    )
    assert "3" in prompt and "4" in prompt and "9" in prompt
    assert "007" in prompt


def test_extract_pdf_text_layer_returns_empty_for_non_pdf():
    from app.shared.infrastructure.documents.text_extraction import extract_pdf_text_layer

    assert extract_pdf_text_layer(b"pas un pdf") == ""
