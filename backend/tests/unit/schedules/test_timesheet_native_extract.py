# backend/tests/unit/schedules/test_timesheet_native_extract.py
"""Extracteur natif : config, lots parallèles, heartbeats, repli déterministe."""

import io

import pytest
from PyPDF2 import PdfWriter

pytestmark = pytest.mark.unit


def _blank_pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=72, height=72)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_mode_native_is_accepted(monkeypatch):
    from app.modules.schedules.application import timesheet_extract_config as cfg

    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "native")
    assert cfg.timesheet_extract_mode() == "native"


def test_batch_size_default_and_clamp(monkeypatch):
    from app.modules.schedules.application import timesheet_extract_config as cfg

    monkeypatch.delenv("TIMESHEET_NATIVE_BATCH_PAGES", raising=False)
    assert cfg.timesheet_native_batch_size() == 4
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "99")
    assert cfg.timesheet_native_batch_size() == 10
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "0")
    assert cfg.timesheet_native_batch_size() == 1


def _canned_batch_payload(page_indices):
    from app.shared.infrastructure.ai.structured_extractor import StructuredExtractionResult

    return StructuredExtractionResult(
        data={
            "pages": [
                {
                    "page_index": idx,
                    "employees": [
                        {
                            "raw_name": f"Emp Page{idx}",
                            "matricule": str(idx).zfill(3),
                            "days": [{"jour": 2, "heures": 7.0}],
                            "weekly_total_pdf": None,
                            "warnings": [],
                        }
                    ],
                    "page_period_hint": None,
                    "confidence": 0.9,
                    "warnings": [],
                }
                for idx in page_indices
            ]
        },
        tokens_used=100,
    )


def test_native_pdf_extraction_merges_batches_and_heartbeats(monkeypatch):
    from app.modules.schedules.application import timesheet_native_extract as native

    async def fake_pdf_extract(**kwargs):
        prompt = kwargs["user_prompt"]
        # Le prompt contient « pages X à Y » — retrouver le lot par ses bornes.
        import re

        start, end = map(int, re.search(r"pages (\d+) à (\d+)", prompt).groups())
        return _canned_batch_payload(list(range(start, end + 1)))

    monkeypatch.setattr(native, "extract_structured_json_from_pdf", fake_pdf_extract)
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "2")
    events = []

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(3),
        filename="releve.pdf",
        year=2026,
        month=6,
        on_progress=events.append,
    )

    assert result.extraction_method == "native_pdf"
    assert result.pages_total == 3 and result.pages_processed == 3
    assert len(result.parse_result.employees) == 3
    assert result.tokens_used == 200  # 2 lots × 100
    phases = [e["phase"] for e in events]
    assert phases[0] == "extracting" and phases[-1] == "merging"
    assert events[-2]["pages_done"] == 3


def test_native_batch_failure_yields_page_warnings(monkeypatch):
    from app.modules.schedules.application import timesheet_native_extract as native

    async def failing_extract(**kwargs):
        return None

    monkeypatch.setattr(native, "extract_structured_json_from_pdf", failing_extract)
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "4")

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(2), filename="r.pdf", year=2026, month=6
    )

    assert result.parse_result.employees == []
    joined = " ".join(w for p in result.page_results for w in p.warnings)
    assert "échouée" in joined


def test_native_pdf_truncation_flagged(monkeypatch):
    """Un PDF plus long que le plafond de lots est signalé tronqué."""
    from app.modules.schedules.application import timesheet_native_extract as native

    async def fake_pdf_extract(**kwargs):
        import re
        start, end = map(int, re.search(r"pages (\d+) à (\d+)", kwargs["user_prompt"]).groups())
        return _canned_batch_payload(list(range(start, end + 1)))

    monkeypatch.setattr(native, "extract_structured_json_from_pdf", fake_pdf_extract)
    monkeypatch.setattr(native, "_real_pdf_page_count", lambda content, fallback: 125)
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "2")

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(3), filename="long.pdf", year=2026, month=6
    )

    assert result.truncated is True
    assert result.pages_total == 125 and result.pages_processed == 3
    assert any("tronqué à 3 pages sur 125" in w for w in result.warnings)


def test_native_batch_partial_payload_warns_missing_pages(monkeypatch):
    """Une réponse qui omet une page du lot produit un avertissement pour cette page."""
    from app.modules.schedules.application import timesheet_native_extract as native

    async def partial_extract(**kwargs):
        import re
        start, _end = map(int, re.search(r"pages (\d+) à (\d+)", kwargs["user_prompt"]).groups())
        return _canned_batch_payload([start])  # seulement la 1re page du lot

    monkeypatch.setattr(native, "extract_structured_json_from_pdf", partial_extract)
    monkeypatch.setenv("TIMESHEET_NATIVE_BATCH_PAGES", "2")

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(2), filename="r.pdf", year=2026, month=6
    )

    warnings_page2 = [w for p in result.page_results if p.page_index == 2 for w in p.warnings]
    assert any("absente" in w for w in warnings_page2)


def test_unsupported_file_format_raises_document_extraction_error():
    """Un fichier non PDF/image (.docx…) ne doit jamais partir en vision — 400 propre."""
    from app.modules.schedules.application import timesheet_native_extract as native
    from app.shared.infrastructure.documents import DocumentExtractionError

    with pytest.raises(DocumentExtractionError):
        native.extract_timesheet_native(
            file_content=b"PK\x03\x04 fake docx bytes",
            filename="releve.docx",
            year=2026,
            month=6,
        )


def test_deterministic_text_layer_short_circuits_llm(monkeypatch):
    """Couche texte Cegid confiante → aucun appel IA (fast path de la spec)."""
    from unittest.mock import AsyncMock

    from app.modules.schedules.application import timesheet_native_extract as native
    from app.modules.schedules.application.parsers.cegid_weekly import (
        CegidDayEntry,
        CegidEmployeeBlock,
        CegidParseResult,
    )
    from types import SimpleNamespace

    block = CegidEmployeeBlock(
        matricule="001",
        raw_name="Emp Direct",
        days=[CegidDayEntry(jour=2, month=6, year=2026, heures=7.0)],
        week_days=[],
        weekly_total_hours=None,
        days_expected_count=1,
        days_parsed_count=1,
        parse_warnings=[],
    )
    det = SimpleNamespace(
        parse_result=CegidParseResult(
            format_detected=True, confidence=0.9, employees=[block]
        ),
        parser_key="cegid_weekly",
    )
    monkeypatch.setattr(native, "extract_pdf_text_layer", lambda _: "SEMAINE 22 ...")
    monkeypatch.setattr(native, "best_deterministic_parse", lambda *a, **k: det)
    mock_llm = AsyncMock()
    monkeypatch.setattr(native, "extract_structured_json_from_pdf", mock_llm)

    result = native.extract_timesheet_native(
        file_content=_blank_pdf(1), filename="cegid.pdf", year=2026, month=6
    )

    mock_llm.assert_not_called()
    assert result.extraction_method == "native_text_layer"
    assert len(result.parse_result.employees) == 1
