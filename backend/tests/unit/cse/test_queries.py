"""
Tests unitaires des queries CSE (application/queries.py).

Les queries utilisent les repositories (infrastructure). On mocke les repositories
pour vérifier les appels et retours sans DB.
"""
from datetime import date, datetime
from unittest.mock import patch, MagicMock

import pytest

from app.modules.cse.application import queries
from app.modules.cse.schemas import ElectedMemberRead, ElectedMemberStatus, DelegationQuotaRead


# --- check_module_active ---


class TestCheckModuleActive:
    """check_module_active (no-op)."""

    def test_does_not_raise(self):
        """Ne lève pas d'exception (toutes les entreprises ont accès)."""
        queries.check_module_active("co-1")


# --- get_elected_members ---


class TestGetElectedMembers:
    """get_elected_members."""

    def test_calls_repository_and_returns_list(self):
        """Appelle elected_member_repository.list_by_company et retourne la liste."""
        mock_members = [MagicMock(), MagicMock()]
        repo = MagicMock()
        repo.list_by_company.return_value = mock_members
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_elected_members("co-1", active_only=True)
        assert result == mock_members
        repo.list_by_company.assert_called_once_with("co-1", active_only=True)

    def test_passes_active_only_false(self):
        """Transmet active_only=False au repository."""
        repo = MagicMock()
        repo.list_by_company.return_value = []
        with patch.object(queries, "elected_member_repository", repo):
            queries.get_elected_members("co-1", active_only=False)
        repo.list_by_company.assert_called_once_with("co-1", active_only=False)


# --- get_elected_member_by_id ---


class TestGetElectedMemberById:
    """get_elected_member_by_id."""

    def test_calls_repository_and_returns_member(self):
        """Appelle get_by_id et retourne l'élu ou l'exception."""
        member = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = member
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_elected_member_by_id("mem-1")
        assert result == member
        repo.get_by_id.assert_called_once_with("mem-1")


# --- get_elected_member_by_employee ---


class TestGetElectedMemberByEmployee:
    """get_elected_member_by_employee."""

    def test_returns_member_when_found(self):
        """Retourne le mandat si trouvé."""
        member = MagicMock()
        repo = MagicMock()
        repo.get_by_employee.return_value = member
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_elected_member_by_employee("co-1", "emp-1")
        assert result == member
        repo.get_by_employee.assert_called_once_with("co-1", "emp-1")

    def test_returns_none_when_not_found(self):
        """Retourne None si pas d'élu pour cet employé."""
        repo = MagicMock()
        repo.get_by_employee.return_value = None
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_elected_member_by_employee("co-1", "emp-99")
        assert result is None


# --- get_mandate_alerts ---


class TestGetMandateAlerts:
    """get_mandate_alerts."""

    def test_calls_repository_with_months_before(self):
        """Appelle get_mandate_alerts avec months_before."""
        alerts = [MagicMock()]
        repo = MagicMock()
        repo.get_mandate_alerts.return_value = alerts
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_mandate_alerts("co-1", months_before=6)
        assert result == alerts
        repo.get_mandate_alerts.assert_called_once_with("co-1", months_before=6)


# --- get_meetings / get_meeting_by_id / get_meeting_participants ---


class TestGetMeetings:
    """get_meetings."""

    def test_calls_meeting_repository_with_filters(self):
        """Appelle list_by_company avec status et meeting_type."""
        meetings = [MagicMock()]
        repo = MagicMock()
        repo.list_by_company.return_value = meetings
        with patch.object(queries, "meeting_repository", repo):
            result = queries.get_meetings(
                "co-1",
                status="terminee",
                meeting_type="ordinaire",
                participant_id="emp-1",
            )
        assert result == meetings
        repo.list_by_company.assert_called_once_with(
            "co-1",
            status="terminee",
            meeting_type="ordinaire",
            participant_id="emp-1",
        )


class TestGetMeetingById:
    """get_meeting_by_id."""

    def test_calls_repository_and_returns_meeting(self):
        """Appelle get_by_id(meeting_id, company_id)."""
        meeting = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = meeting
        with patch.object(queries, "meeting_repository", repo):
            result = queries.get_meeting_by_id("mtg-1", "co-1")
        assert result == meeting
        repo.get_by_id.assert_called_once_with("mtg-1", "co-1")


class TestGetMeetingParticipants:
    """get_meeting_participants."""

    def test_calls_repository_and_returns_list(self):
        """Appelle get_participants(meeting_id)."""
        participants = [MagicMock()]
        repo = MagicMock()
        repo.get_participants.return_value = participants
        with patch.object(queries, "meeting_repository", repo):
            result = queries.get_meeting_participants("mtg-1")
        assert result == participants
        repo.get_participants.assert_called_once_with("mtg-1")


# --- get_recording_status ---


class TestGetRecordingStatus:
    """get_recording_status."""

    def test_calls_recording_repository(self):
        """Appelle recording_repository.get_status."""
        status = MagicMock()
        repo = MagicMock()
        repo.get_status.return_value = status
        with patch.object(queries, "recording_repository", repo):
            result = queries.get_recording_status("mtg-1")
        assert result == status
        repo.get_status.assert_called_once_with("mtg-1")


# --- get_delegation_quota / get_delegation_hours / get_delegation_summary ---


class TestGetDelegationQuota:
    """get_delegation_quota."""

    def test_calls_repository_and_returns_quota_or_none(self):
        """Appelle get_quota(company_id, employee_id)."""
        quota = MagicMock()
        repo = MagicMock()
        repo.get_quota.return_value = quota
        with patch.object(queries, "delegation_repository", repo):
            result = queries.get_delegation_quota("co-1", "emp-1")
        assert result == quota
        repo.get_quota.assert_called_once_with("co-1", "emp-1")

    def test_returns_none_when_no_quota(self):
        """Retourne None si pas de quota."""
        repo = MagicMock()
        repo.get_quota.return_value = None
        with patch.object(queries, "delegation_repository", repo):
            result = queries.get_delegation_quota("co-1", "emp-99")
        assert result is None


class TestGetDelegationHours:
    """get_delegation_hours."""

    def test_calls_repository_with_period(self):
        """Appelle list_hours avec period_start et period_end."""
        hours = [MagicMock()]
        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        repo = MagicMock()
        repo.list_hours.return_value = hours
        with patch.object(queries, "delegation_repository", repo):
            result = queries.get_delegation_hours(
                "co-1", "emp-1", period_start=start, period_end=end
            )
        assert result == hours
        repo.list_hours.assert_called_once_with("co-1", "emp-1", start, end)


class TestGetDelegationSummary:
    """get_delegation_summary."""

    def test_calls_repository_with_dates(self):
        """Appelle get_summary(company_id, period_start, period_end)."""
        summary = [MagicMock()]
        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        repo = MagicMock()
        repo.get_summary.return_value = summary
        with patch.object(queries, "delegation_repository", repo):
            result = queries.get_delegation_summary("co-1", start, end)
        assert result == summary
        repo.get_summary.assert_called_once_with("co-1", start, end)


# --- get_bdes_documents / get_bdes_document_by_id ---


class TestGetBdesDocuments:
    """get_bdes_documents."""

    def test_calls_repository_with_filters(self):
        """Appelle list_by_company avec year, document_type, visible_to_elected_only."""
        docs = [MagicMock()]
        repo = MagicMock()
        repo.list_by_company.return_value = docs
        with patch.object(queries, "bdes_document_repository", repo):
            result = queries.get_bdes_documents(
                "co-1",
                year=2024,
                document_type="bdes",
                visible_to_elected_only=True,
            )
        assert result == docs
        repo.list_by_company.assert_called_once_with(
            "co-1",
            year=2024,
            document_type="bdes",
            visible_to_elected_only=True,
        )


class TestGetBdesDocumentById:
    """get_bdes_document_by_id."""

    def test_calls_repository_and_returns_document(self):
        """Appelle get_by_id(document_id, company_id)."""
        doc = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = doc
        with patch.object(queries, "bdes_document_repository", repo):
            result = queries.get_bdes_document_by_id("doc-1", "co-1")
        assert result == doc
        repo.get_by_id.assert_called_once_with("doc-1", "co-1")


# --- get_election_cycles / get_election_cycle_by_id / get_election_alerts ---


class TestGetElectionCycles:
    """get_election_cycles."""

    def test_calls_repository_and_returns_list(self):
        """Appelle list_by_company(company_id)."""
        cycles = [MagicMock()]
        repo = MagicMock()
        repo.list_by_company.return_value = cycles
        with patch.object(queries, "election_cycle_repository", repo):
            result = queries.get_election_cycles("co-1")
        assert result == cycles
        repo.list_by_company.assert_called_once_with("co-1")


class TestGetElectionCycleById:
    """get_election_cycle_by_id."""

    def test_calls_repository_and_returns_cycle(self):
        """Appelle get_by_id(cycle_id, company_id)."""
        cycle = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = cycle
        with patch.object(queries, "election_cycle_repository", repo):
            result = queries.get_election_cycle_by_id("cycle-1", "co-1")
        assert result == cycle
        repo.get_by_id.assert_called_once_with("cycle-1", "co-1")


class TestGetElectionAlerts:
    """get_election_alerts."""

    def test_calls_repository_and_returns_alerts(self):
        """Appelle get_election_alerts(company_id)."""
        alerts = [MagicMock()]
        repo = MagicMock()
        repo.get_election_alerts.return_value = alerts
        with patch.object(queries, "election_cycle_repository", repo):
            result = queries.get_election_alerts("co-1")
        assert result == alerts
        repo.get_election_alerts.assert_called_once_with("co-1")


# --- is_elected_member ---


class TestIsElectedMember:
    """is_elected_member."""

    def test_returns_true_when_elected(self):
        """Retourne True si l'employé est élu actif."""
        repo = MagicMock()
        repo.is_elected.return_value = True
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.is_elected_member("co-1", "emp-1")
        assert result is True
        repo.is_elected.assert_called_once_with("co-1", "emp-1")

    def test_returns_false_when_not_elected(self):
        """Retourne False si l'employé n'est pas élu."""
        repo = MagicMock()
        repo.is_elected.return_value = False
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.is_elected_member("co-1", "emp-99")
        assert result is False


# --- get_my_elected_status ---


class TestGetMyElectedStatus:
    """get_my_elected_status."""

    def test_returns_status_with_mandate_when_elected(self):
        """Si un mandat existe, retourne ElectedMemberStatus avec is_elected=True."""
        mandate = ElectedMemberRead(
            id="mem-1",
            company_id="co-1",
            employee_id="emp-1",
            role="titulaire",
            college="ouvriers",
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
            is_active=True,
            notes=None,
            created_at=datetime(2024, 1, 1),
            updated_at=datetime(2024, 1, 1),
            first_name="Jean",
            last_name="Dupont",
            job_title="Agent",
        )
        repo = MagicMock()
        repo.get_by_employee.return_value = mandate
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_my_elected_status("co-1", "emp-1")
        assert isinstance(result, ElectedMemberStatus)
        assert result.is_elected is True
        assert result.current_mandate == mandate
        assert result.role == "titulaire"

    def test_returns_status_without_mandate_when_not_elected(self):
        """Si pas de mandat, retourne is_elected=False, role=None."""
        repo = MagicMock()
        repo.get_by_employee.return_value = None
        with patch.object(queries, "elected_member_repository", repo):
            result = queries.get_my_elected_status("co-1", "emp-99")
        assert result.is_elected is False
        assert result.current_mandate is None
        assert result.role is None


# --- list_delegation_quotas ---


class TestListDelegationQuotas:
    """list_delegation_quotas."""

    def test_calls_repository_and_returns_list_of_quota_read(self):
        """Appelle list_quotas et retourne une liste de DelegationQuotaRead."""
        quotas = [MagicMock(spec=DelegationQuotaRead)]
        repo = MagicMock()
        repo.list_quotas.return_value = quotas
        with patch.object(queries, "delegation_repository", repo):
            result = queries.list_delegation_quotas("co-1")
        assert result == quotas
        repo.list_quotas.assert_called_once_with("co-1")


# --- get_meeting_minutes_path ---


class TestGetMeetingMinutesPath:
    """get_meeting_minutes_path."""

    def test_calls_recording_repository_and_returns_path_or_none(self):
        """Appelle get_minutes_path(meeting_id, company_id)."""
        repo = MagicMock()
        repo.get_minutes_path.return_value = "path/to/pv.pdf"
        with patch.object(queries, "recording_repository", repo):
            result = queries.get_meeting_minutes_path("mtg-1", "co-1")
        assert result == "path/to/pv.pdf"
        repo.get_minutes_path.assert_called_once_with("mtg-1", "co-1")

    def test_returns_none_when_no_minutes(self):
        """Retourne None si pas de PV."""
        repo = MagicMock()
        repo.get_minutes_path.return_value = None
        with patch.object(queries, "recording_repository", repo):
            result = queries.get_meeting_minutes_path("mtg-1", "co-1")
        assert result is None
