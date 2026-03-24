"""
Tests d'intégration du repository schedules (ScheduleRepository).

Vérifie que le repository délègue correctement aux appels Supabase et retourne
les données attendues. Les appels DB sont mockés (pas de DB réelle).
Pour des tests contre une DB de test, prévoir db_session et données dans
employee_schedules, employees, companies.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.schedules.infrastructure.repository import ScheduleRepository


pytestmark = pytest.mark.integration


@pytest.fixture
def repo():
    """Instance du repository à tester."""
    return ScheduleRepository()


class TestScheduleRepositoryGetPlannedCalendar:
    """get_planned_calendar."""

    def test_calls_supabase_and_returns_planned_calendar(self, repo: ScheduleRepository):
        """Délègue à Supabase match employee_id, year, month ; retourne planned_calendar."""
        mock_data = {"planned_calendar": {"calendrier_prevu": [{"jour": 1, "type": "work"}]}}
        mock_response = MagicMock()
        mock_response.data = mock_data

        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = mock_response
            chain.match.return_value = chain
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.get_planned_calendar("emp-1", 2025, 3)

        assert result is not None
        assert result.get("calendrier_prevu") == [{"jour": 1, "type": "work"}]
        supabase.table.assert_called_once_with("employee_schedules")
        chain.select.assert_called_once_with("planned_calendar")
        chain.match.assert_called_once_with({"employee_id": "emp-1", "year": 2025, "month": 3})

    def test_returns_none_when_no_row(self, repo: ScheduleRepository):
        """Pas de ligne → None (maybe_single retourne None)."""
        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = None
            chain.match.return_value = chain
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.get_planned_calendar("emp-unknown", 2025, 3)

        assert result is None


class TestScheduleRepositoryGetActualHours:
    """get_actual_hours."""

    def test_returns_actual_hours_from_row(self, repo: ScheduleRepository):
        """Retourne actual_hours extrait de la ligne."""
        mock_data = {"actual_hours": {"calendrier_reel": [{"jour": 1, "heures_faites": 7.5}]}}
        mock_response = MagicMock()
        mock_response.data = mock_data

        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = mock_response
            chain.match.return_value = chain
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.get_actual_hours("emp-1", 2025, 3)

        assert result is not None
        assert result.get("calendrier_reel") == [{"jour": 1, "heures_faites": 7.5}]


class TestScheduleRepositoryUpsertSchedule:
    """upsert_schedule."""

    def test_calls_upsert_with_correct_payload(self, repo: ScheduleRepository):
        """Upsert avec employee_id, company_id, year, month et champs optionnels."""
        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            supabase.table.return_value = chain

            repo.upsert_schedule(
                "emp-1",
                "comp-1",
                2025,
                3,
                planned_calendar={"calendrier_prevu": []},
            )

        chain.upsert.assert_called_once()
        call_args = chain.upsert.call_args[0][0]
        assert call_args["employee_id"] == "emp-1"
        assert call_args["company_id"] == "comp-1"
        assert call_args["year"] == 2025
        assert call_args["month"] == 3
        assert "planned_calendar" in call_args
        assert call_args["planned_calendar"] == {"calendrier_prevu": []}


class TestScheduleRepositoryGetSchedulesForMonths:
    """get_schedules_for_months."""

    def test_returns_empty_list_when_year_months_empty(self, repo: ScheduleRepository):
        """year_months vide → [] sans appel Supabase."""
        result = repo.get_schedules_for_months("emp-1", [])
        assert result == []

    def test_calls_supabase_in_and_returns_data(self, repo: ScheduleRepository):
        """Délègue avec .in_('year', ...).in_('month', ...), retourne data."""
        mock_data = [
            {"year": 2025, "month": 2, "planned_calendar": None, "actual_hours": None},
            {"year": 2025, "month": 3, "planned_calendar": {}, "actual_hours": {}},
        ]
        mock_response = MagicMock()
        mock_response.data = mock_data

        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.in_.return_value = chain
            chain.eq.return_value = chain
            chain.execute.return_value = mock_response
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.get_schedules_for_months(
                "emp-1",
                [(2025, 2), (2025, 3)],
            )

        assert result == mock_data
        chain.eq.assert_called_once_with("employee_id", "emp-1")


class TestScheduleRepositoryGetLatestCumulsRow:
    """get_latest_cumuls_row."""

    def test_returns_row_with_cumuls_ordered_desc(self, repo: ScheduleRepository):
        """Dernière ligne avec cumuls non null (order year desc, month desc)."""
        mock_data = {"cumuls": {"periode": {"annee_en_cours": 2025}, "cumuls": {}}}
        mock_response = MagicMock()
        mock_response.data = mock_data

        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.not_.is_.return_value = chain
            chain.order.return_value = chain
            chain.limit.return_value = chain
            chain.maybe_single.return_value.execute.return_value = mock_response
            chain.eq.return_value = chain
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.get_latest_cumuls_row("emp-1")

        assert result == mock_data
        chain.eq.assert_called_once_with("employee_id", "emp-1")
        chain.order.assert_any_call("year", desc=True)
        chain.order.assert_any_call("month", desc=True)
        chain.limit.assert_called_once_with(1)


class TestScheduleRepositoryExistsSchedule:
    """exists_schedule."""

    def test_returns_true_when_row_exists(self, repo: ScheduleRepository):
        """Ligne existante → True."""
        mock_response = MagicMock()
        mock_response.data = {"id": "some-uuid"}

        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = mock_response
            chain.match.return_value = chain
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.exists_schedule("emp-1", 2025, 3)

        assert result is True

    def test_returns_false_when_no_row(self, repo: ScheduleRepository):
        """Pas de ligne → False."""
        mock_response = MagicMock()
        mock_response.data = None

        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = mock_response
            chain.match.return_value = chain
            chain.select.return_value = chain
            supabase.table.return_value = chain

            result = repo.exists_schedule("emp-unknown", 2025, 3)

        assert result is False


class TestScheduleRepositoryInsertSchedule:
    """insert_schedule."""

    def test_calls_insert_with_full_payload(self, repo: ScheduleRepository):
        """Insert avec planned_calendar obligatoire, actual_hours/payroll_events/cumuls optionnels."""
        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            supabase.table.return_value = chain

            repo.insert_schedule(
                "emp-1",
                "comp-1",
                2025,
                3,
                planned_calendar={"calendrier_prevu": [{"jour": 1, "type": "work"}]},
            )

        chain.insert.assert_called_once()
        payload = chain.insert.call_args[0][0]
        assert payload["employee_id"] == "emp-1"
        assert payload["company_id"] == "comp-1"
        assert payload["year"] == 2025
        assert payload["month"] == 3
        assert payload["planned_calendar"] == {"calendrier_prevu": [{"jour": 1, "type": "work"}]}
        assert payload["actual_hours"] == {}
        assert payload["payroll_events"] == {}
        assert payload["cumuls"] == {}


class TestScheduleRepositoryUpdatePlannedCalendarOnly:
    """update_planned_calendar_only."""

    def test_calls_update_with_match(self, repo: ScheduleRepository):
        """Update planned_calendar pour employee_id, year, month."""
        with patch(
            "app.modules.schedules.infrastructure.repository.supabase",
        ) as supabase:
            chain = MagicMock()
            chain.update.return_value = chain
            chain.match.return_value = chain
            chain.execute.return_value = None
            supabase.table.return_value = chain

            repo.update_planned_calendar_only(
                "emp-1",
                2025,
                3,
                {"calendrier_prevu": []},
            )

        chain.update.assert_called_once_with({"planned_calendar": {"calendrier_prevu": []}})
        chain.match.assert_called_once_with(
            {"employee_id": "emp-1", "year": 2025, "month": 3}
        )
