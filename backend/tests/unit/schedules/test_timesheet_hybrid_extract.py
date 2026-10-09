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


def _handwritten_employee(name: str) -> dict:
    return {
        "raw_name": name,
        "matricule": None,
        "week_number": 18,
        "weekly_total_pdf": None,
        "days": [
            {
                "weekday": "lundi",
                "debut": "08:00",
                "fin": "17:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "mardi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "mercredi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "jeudi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
        ],
    }


@pytest.fixture
def minimal_png() -> bytes:
    from PIL import Image
    import io

    img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.is_llm_configured",
    return_value=True,
)
@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json_from_image"
)
@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json"
)
@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.render_document_pages"
)
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
    mock_vision_llm.return_value = StructuredExtractionResult(
        data=payload, tokens_used=50
    )
    mock_text_llm.return_value = StructuredExtractionResult(
        data=payload, tokens_used=40
    )

    result = extract_timesheet_hybrid(
        file_content=b"fake",
        filename="test.pdf",
        year=2026,
        month=5,
    )
    assert len(result.parse_result.employees) >= 1
    assert result.tokens_used == 50
    assert result.extraction_method == "hybrid_vision_ocr"


@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.is_llm_configured",
    return_value=True,
)
@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json_from_image"
)
@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.extract_structured_json"
)
@patch(
    "app.modules.schedules.application.timesheet_hybrid_extract.render_document_pages"
)
def test_hybrid_extract_handwritten_weekly_mock(
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
                ocr_text="S18 LUNDI MARDI MERCREDI JEUDI VENDREDI DEBUT FIN",
            )
        ],
        pages_total=1,
        pages_processed=1,
    )
    payload = {
        "employees": [
            _handwritten_employee("HUGO"),
            _handwritten_employee("MICHEL"),
            _handwritten_employee("ANTHONY"),
            _handwritten_employee("LEO"),
            _handwritten_employee("AURELIEN"),
            _handwritten_employee("MARION"),
        ],
        "page_period_hint": "S18",
        "confidence": 0.88,
        "warnings": [],
    }
    mock_vision_llm.return_value = StructuredExtractionResult(
        data=payload, tokens_used=55
    )
    mock_text_llm.return_value = None

    result = extract_timesheet_hybrid(
        file_content=b"fake",
        filename="semaine 18.pdf",
        year=2026,
        month=5,
    )

    names = [emp.raw_name for emp in result.parse_result.employees]
    total_days = sum(len(emp.days) for emp in result.parse_result.employees)
    assert names == ["HUGO", "MICHEL", "ANTHONY", "LEO", "AURELIEN", "MARION"]
    assert total_days >= 20
    assert all(
        day.heures > 0 for emp in result.parse_result.employees for day in emp.days
    )


def test_une_heure_negative_lue_est_signalee_des_l_extraction():
    """Import S29 Colorplast : −10,5 h lues pour Lanolet le 16/07 (plages
    DÉBUT/FIN inversées). La valeur reste visible à la relecture, mais le
    salarié porte un avertissement qui nomme le jour."""
    from app.modules.schedules.application.timesheet_hybrid_extract import (
        _merged_to_cegid_result,
    )
    from app.modules.schedules.application.timesheet_page_merge import (
        MergedEmployee,
        MergedExtractionResult,
    )

    merged = MergedExtractionResult(
        employees=[
            MergedEmployee(
                raw_name="LANOLET",
                days=[
                    {"jour": 16, "heures": -10.5, "type": "travail"},
                    {"jour": 17, "heures": 8.0, "type": "travail"},
                ],
            )
        ],
        confidence=0.9,
    )

    bloc = _merged_to_cegid_result(merged, target_year=2026, target_month=7).employees[0]

    assert [d.heures for d in bloc.days] == [-10.5, 8.0]
    assert any("16" in w and "négative" in w for w in bloc.parse_warnings), bloc.parse_warnings


def test_un_jour_non_lu_n_est_jamais_transforme_en_zero_heure():
    """Relevé PDF à couverture 3/5 (09/10/2026) : les jours que la feuille ne permet
    pas de lire étaient écrits à 0 h. Un jour non lu reste absent de la proposition
    (il reste à saisir au calendrier) ; un 0 h lu explicitement est conservé."""
    from app.modules.schedules.application.timesheet_hybrid_extract import (
        _merged_to_cegid_result,
    )
    from app.modules.schedules.application.timesheet_page_merge import (
        MergedEmployee,
        MergedExtractionResult,
    )

    merged = MergedExtractionResult(
        employees=[
            MergedEmployee(
                raw_name="VASSEUR Élodie",
                days=[
                    {"jour": 14, "heures": 7.0, "type": "travail"},
                    {"jour": 15, "heures": None, "type": "travail"},
                    {"jour": 16, "heures": 0.0, "type": "travail"},
                    {"jour": 17, "heures": None, "type": "travail"},
                    {"jour": 18, "heures": 7.0, "type": "travail"},
                ],
            )
        ],
        confidence=0.9,
    )

    bloc = _merged_to_cegid_result(merged, target_year=2026, target_month=10).employees[0]

    assert [(d.jour, d.heures) for d in bloc.days] == [(14, 7.0), (16, 0.0), (18, 7.0)]
    assert bloc.days_expected_count == 5
    assert bloc.days_parsed_count == 3
