"""Tests routing TIMESHEET_EXTRACT_MODE."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def deterministic_mode(monkeypatch):
    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "deterministic")


def test_timesheet_extract_mode_default_hybrid(monkeypatch):
    monkeypatch.delenv("TIMESHEET_EXTRACT_MODE", raising=False)
    from app.modules.schedules.application.timesheet_extract_config import (
        timesheet_extract_mode,
    )

    assert timesheet_extract_mode() == "hybrid"


def test_timesheet_extract_mode_deterministic(monkeypatch):
    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "deterministic")
    from app.modules.schedules.application.timesheet_extract_config import (
        timesheet_extract_mode,
    )

    assert timesheet_extract_mode() == "deterministic"


@patch("app.modules.schedules.application.ai_fill._extract_timesheet_hybrid_path")
@patch("app.modules.schedules.application.roster_enrichment.enrich_roster_time_tracking_ids")
def test_extract_timesheet_routes_hybrid(mock_enrich, mock_hybrid, monkeypatch):
    monkeypatch.setenv("TIMESHEET_EXTRACT_MODE", "hybrid")
    from app.modules.schedules.application.ai_fill import extract_timesheet
    from app.modules.schedules.schemas.ai import AiCalendarProposalResponse, RosterEmployee

    mock_enrich.side_effect = lambda roster, _cid: roster
    mock_hybrid.return_value = AiCalendarProposalResponse(
        year=2026, month=5, source="test"
    )

    result = extract_timesheet(
        year=2026,
        month=5,
        file_content=b"x",
        filename="t.pdf",
        roster=[RosterEmployee(id="1", first_name="A", last_name="B")],
    )
    mock_hybrid.assert_called_once()
    assert result.year == 2026
