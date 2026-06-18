"""Tests consensus vision/OCR par page."""

from app.modules.schedules.application.timesheet_page_consensus import (
    build_page_consensus,
)


def test_consensus_matching_matricules():
    vision = {
        "employees": [
            {
                "raw_name": "DUPONT Jean",
                "matricule": "42",
                "weekly_total_pdf": 35.0,
                "days": [{"jour": 25, "heures": 7.0, "type": "travail"}],
            }
        ],
        "page_period_hint": "SEMAINE 22",
        "confidence": 0.9,
        "warnings": [],
    }
    text = {
        "employees": [
            {
                "raw_name": "DUPONT Jean",
                "matricule": "42",
                "weekly_total_pdf": 35.0,
                "days": [{"jour": 25, "heures": 7.1, "type": "travail"}],
            }
        ],
        "confidence": 0.85,
        "warnings": [],
    }
    result = build_page_consensus(
        page_index=1, vision_data=vision, text_data=text, tokens_used=100
    )
    assert len(result.employees) == 1
    assert result.employees[0].matricule == "42"
    assert result.conflicts_count == 0


def test_consensus_hours_mismatch():
    vision = {
        "employees": [
            {
                "raw_name": "MARTIN Paul",
                "matricule": "10",
                "weekly_total_pdf": None,
                "days": [{"jour": 26, "heures": 8.0, "type": "travail"}],
            }
        ],
        "confidence": 0.9,
        "warnings": [],
    }
    text = {
        "employees": [
            {
                "raw_name": "MARTIN Paul",
                "matricule": "10",
                "weekly_total_pdf": None,
                "days": [{"jour": 26, "heures": 4.0, "type": "travail"}],
            }
        ],
        "confidence": 0.7,
        "warnings": [],
    }
    result = build_page_consensus(
        page_index=2, vision_data=vision, text_data=text
    )
    assert result.conflicts_count >= 1
    assert result.employees[0].days[0]["heures"] == 8.0


def test_consensus_ignores_junk_text():
    text = {
        "employees": [
            {
                "raw_name": "Édition en heures et minutes",
                "matricule": None,
                "weekly_total_pdf": None,
                "days": [],
            }
        ],
        "confidence": 0.5,
        "warnings": [],
    }
    vision = {
        "employees": [
            {
                "raw_name": "BERGER Anne",
                "matricule": "5",
                "weekly_total_pdf": 35.0,
                "days": [{"jour": 27, "heures": 7.0, "type": "travail"}],
            }
        ],
        "confidence": 0.85,
        "warnings": [],
    }
    result = build_page_consensus(
        page_index=1, vision_data=vision, text_data=text
    )
    assert len(result.employees) == 1
    assert result.employees[0].raw_name == "BERGER Anne"


def test_consensus_single_channel_vision():
    result = build_page_consensus(
        page_index=1,
        vision_data={
            "employees": [
                {
                    "raw_name": "LIKA Rina",
                    "matricule": "95",
                    "weekly_total_pdf": 35.0,
                    "days": [{"jour": 28, "heures": 7.5, "type": "travail"}],
                }
            ],
            "confidence": 0.8,
            "warnings": [],
        },
        text_data=None,
    )
    assert len(result.employees) == 1
    assert result.conflicts_count == 0
    assert not any("single_channel" in w for w in result.warnings)
