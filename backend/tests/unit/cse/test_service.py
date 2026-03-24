"""
Tests unitaires du service applicatif CSE (application/service.py).

Export fichiers, _parse_date, get_meeting_minutes_path_or_raise.
On mocke queries et providers (cse_export_provider, cse_pdf_provider).
"""
from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException

from app.modules.cse.application.service import (
    export_elected_members_file,
    export_delegation_hours_file,
    export_meetings_history_file,
    export_minutes_annual_file,
    export_election_calendar_file,
    get_meeting_minutes_path_or_raise,
)
from app.modules.cse.application.dto import ExportFile


# --- export_elected_members_file ---


class TestExportElectedMembersFile:
    """export_elected_members_file."""

    def test_returns_export_file_with_xlsx_content(self):
        """Appelle get_elected_members, export_provider, retourne ExportFile."""
        members = [MagicMock()]
        members[0].model_dump = lambda: {"id": "mem-1", "role": "titulaire"}
        content = b"xlsx-bytes"
        with patch(
            "app.modules.cse.application.service.queries.get_elected_members",
            return_value=members,
        ), patch(
            "app.modules.cse.application.service.cse_export_provider.export_elected_members",
            return_value=content,
        ):
            result = export_elected_members_file("co-1")
        assert isinstance(result, ExportFile)
        assert result.content == content
        assert result.filename == "base_elus_cse.xlsx"
        assert "spreadsheet" in result.media_type

    def test_calls_queries_with_active_only_false(self):
        """Demande tous les élus (active_only=False) pour l'export."""
        with patch(
            "app.modules.cse.application.service.queries.get_elected_members",
            return_value=[],
        ) as mock_get, patch(
            "app.modules.cse.application.service.cse_export_provider.export_elected_members",
            return_value=b"",
        ):
            export_elected_members_file("co-1")
        mock_get.assert_called_once_with("co-1", active_only=False)


# --- export_delegation_hours_file ---


class TestExportDelegationHoursFile:
    """export_delegation_hours_file."""

    def test_uses_current_month_when_no_dates(self):
        """Sans period_start/end, utilise le mois en cours."""
        with patch(
            "app.modules.cse.application.service.queries.get_elected_members",
            return_value=[],
        ), patch(
            "app.modules.cse.application.service.queries.get_delegation_summary",
            return_value=[],
        ), patch(
            "app.modules.cse.application.service.cse_export_provider.export_delegation_hours",
            return_value=b"xlsx",
        ):
            result = export_delegation_hours_file("co-1")
        assert isinstance(result, ExportFile)
        assert result.filename == "heures_delegation_cse.xlsx"

    def test_uses_provided_period_dates(self):
        """Avec period_start et period_end, les utilise."""
        start = date(2024, 2, 1)
        end = date(2024, 2, 29)
        mock_summary = MagicMock()
        with patch(
            "app.modules.cse.application.service.queries.get_elected_members",
            return_value=[],
        ), patch(
            "app.modules.cse.application.service.queries.get_delegation_hours",
            return_value=[],
        ), patch(
            "app.modules.cse.application.service.queries.get_delegation_summary",
            mock_summary,
        ), patch(
            "app.modules.cse.application.service.cse_export_provider.export_delegation_hours",
            return_value=b"xlsx",
        ):
            result = export_delegation_hours_file(
                "co-1", period_start=start, period_end=end
            )
        assert result.content == b"xlsx"
        mock_summary.assert_called_once_with("co-1", start, end)


# --- export_meetings_history_file ---


class TestExportMeetingsHistoryFile:
    """export_meetings_history_file."""

    def test_returns_export_file_with_meetings(self):
        """Appelle get_meetings, export_provider, retourne ExportFile."""
        meetings = [MagicMock()]
        meetings[0].model_dump = lambda: {"id": "mtg-1", "title": "CSE"}
        with patch(
            "app.modules.cse.application.service.queries.get_meetings",
            return_value=meetings,
        ), patch(
            "app.modules.cse.application.service.cse_export_provider.export_meetings_history",
            return_value=b"xlsx",
        ):
            result = export_meetings_history_file("co-1")
        assert isinstance(result, ExportFile)
        assert result.filename == "historique_reunions_cse.xlsx"
        assert result.content == b"xlsx"


# --- export_minutes_annual_file ---


class TestExportMinutesAnnualFile:
    """export_minutes_annual_file."""

    def test_raises_404_when_no_minutes_for_year(self):
        """Aucun PV pour l'année → HTTPException 404."""
        with patch(
            "app.modules.cse.application.service.queries.get_meetings",
            return_value=[],
        ):
            with pytest.raises(HTTPException) as exc_info:
                export_minutes_annual_file("co-1", 2024)
        assert exc_info.value.status_code == 404
        assert "Aucun PV" in exc_info.value.detail

    def test_raises_404_when_meetings_have_no_minutes_path(self):
        """Réunions présentes mais sans PV → 404."""
        meeting = MagicMock()
        meeting.meeting_date = "2024-03-15"
        meeting.id = "mtg-1"
        with patch(
            "app.modules.cse.application.service.queries.get_meetings",
            return_value=[meeting],
        ), patch(
            "app.modules.cse.application.service.queries.get_meeting_minutes_path",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                export_minutes_annual_file("co-1", 2024)
        assert exc_info.value.status_code == 404

    def test_returns_pdf_when_first_meeting_has_minutes(self):
        """Première réunion de l'année avec PV → génère PDF."""
        meeting = MagicMock()
        meeting.meeting_date = "2024-03-15"
        meeting.id = "mtg-1"
        meeting.model_dump = lambda: {"id": "mtg-1", "meeting_date": "2024-03-15"}
        with patch(
            "app.modules.cse.application.service.queries.get_meetings",
            return_value=[meeting],
        ), patch(
            "app.modules.cse.application.service.queries.get_meeting_minutes_path",
            return_value="/path/to/pv.pdf",
        ), patch(
            "app.modules.cse.application.service.queries.get_meeting_by_id",
            return_value=meeting,
        ), patch(
            "app.modules.cse.application.service.cse_pdf_provider.generate_minutes",
            return_value=b"%PDF-1.4",
        ):
            result = export_minutes_annual_file("co-1", 2024)
        assert isinstance(result, ExportFile)
        assert result.content == b"%PDF-1.4"
        assert "pv_annuels_2024" in result.filename
        assert result.media_type == "application/pdf"


# --- export_election_calendar_file ---


class TestExportElectionCalendarFile:
    """export_election_calendar_file."""

    def test_raises_404_when_no_cycles(self):
        """Aucun cycle électoral → HTTPException 404."""
        with patch(
            "app.modules.cse.application.service.queries.get_election_cycles",
            return_value=[],
        ):
            with pytest.raises(HTTPException) as exc_info:
                export_election_calendar_file("co-1")
        assert exc_info.value.status_code == 404
        assert "cycle" in exc_info.value.detail.lower()

    def test_uses_most_recent_cycle_when_no_cycle_id(self):
        """Sans cycle_id, utilise le premier cycle (le plus récent)."""
        cycle = MagicMock()
        cycle.cycle_name = "2024-2026"
        cycle.model_dump = lambda: {"cycle_name": "2024-2026", "timeline": []}
        with patch(
            "app.modules.cse.application.service.queries.get_election_cycles",
            return_value=[cycle],
        ), patch(
            "app.modules.cse.application.service.cse_pdf_provider.generate_election_calendar",
            return_value=b"%PDF",
        ):
            result = export_election_calendar_file("co-1")
        assert result.content == b"%PDF"
        assert "calendrier_electoral" in result.filename

    def test_uses_cycle_id_when_provided(self):
        """Avec cycle_id, utilise get_election_cycle_by_id."""
        cycle = MagicMock()
        cycle.cycle_name = "Custom"
        cycle.model_dump = lambda: {"cycle_name": "Custom", "timeline": []}
        with patch(
            "app.modules.cse.application.service.queries.get_election_cycle_by_id",
            return_value=cycle,
        ), patch(
            "app.modules.cse.application.service.cse_pdf_provider.generate_election_calendar",
            return_value=b"%PDF",
        ):
            result = export_election_calendar_file("co-1", cycle_id="cycle-1")
        assert result.content == b"%PDF"


# --- get_meeting_minutes_path_or_raise ---


class TestGetMeetingMinutesPathOrRaise:
    """get_meeting_minutes_path_or_raise."""

    def test_returns_path_when_present(self):
        """Si un chemin existe, le retourne."""
        with patch(
            "app.modules.cse.application.service.queries.get_meeting_minutes_path",
            return_value="path/to/pv.pdf",
        ):
            result = get_meeting_minutes_path_or_raise("mtg-1", "co-1")
        assert result == "path/to/pv.pdf"

    def test_raises_404_when_no_path(self):
        """Pas de PV → HTTPException 404."""
        with patch(
            "app.modules.cse.application.service.queries.get_meeting_minutes_path",
            return_value=None,
        ):
            with pytest.raises(HTTPException) as exc_info:
                get_meeting_minutes_path_or_raise("mtg-1", "co-1")
        assert exc_info.value.status_code == 404
        assert "PV" in exc_info.value.detail
