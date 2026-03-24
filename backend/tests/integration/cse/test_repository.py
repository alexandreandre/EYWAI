"""
Tests d'intégration des repositories CSE.

Vérifient que chaque repository délègue correctement à cse_service_impl
ou aux queries infrastructure (fetch_delegation_quotas_for_company, fetch_meeting_minutes_path).
Les appels DB sont mockés (pas de DB réelle).
Pour des tests contre une DB de test, prévoir db_session et données dans
cse_elected_members, cse_meetings, cse_meeting_recordings, cse_delegation_quotas, etc.
"""
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

from app.modules.cse.infrastructure.repository import (
    ElectedMemberRepository,
    MeetingRepository,
    RecordingRepository,
    DelegationRepository,
    BDESDocumentRepository,
    ElectionCycleRepository,
)


pytestmark = pytest.mark.integration


# --- ElectedMemberRepository ---


class TestElectedMemberRepository:
    """ElectedMemberRepository délègue à cse_service_impl."""

    def test_list_by_company_calls_impl(self):
        repo = ElectedMemberRepository()
        data = [{"id": "mem-1", "role": "titulaire"}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_elected_members",
            return_value=data,
        ) as mock:
            result = repo.list_by_company("co-1", active_only=True)
            mock.assert_called_once_with("co-1", active_only=True)
        assert result == data

    def test_get_by_id_calls_impl(self):
        repo = ElectedMemberRepository()
        member = {"id": "mem-1", "employee_id": "emp-1"}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_elected_member_by_id",
            return_value=member,
        ) as mock:
            result = repo.get_by_id("mem-1")
            mock.assert_called_once_with("mem-1")
        assert result == member

    def test_get_by_employee_calls_impl(self):
        repo = ElectedMemberRepository()
        member = {"id": "mem-1", "employee_id": "emp-1"}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_elected_member_by_employee",
            return_value=member,
        ) as mock:
            result = repo.get_by_employee("co-1", "emp-1")
            mock.assert_called_once_with("co-1", "emp-1")
        assert result == member

    def test_is_elected_calls_impl(self):
        repo = ElectedMemberRepository()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl._is_elected_member",
            return_value=True,
        ) as mock:
            result = repo.is_elected("co-1", "emp-1")
            mock.assert_called_once_with("co-1", "emp-1")
        assert result is True

    def test_get_mandate_alerts_calls_impl(self):
        repo = ElectedMemberRepository()
        alerts = [{"elected_member_id": "mem-1", "days_remaining": 30}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_mandate_alerts",
            return_value=alerts,
        ) as mock:
            result = repo.get_mandate_alerts("co-1", months_before=6)
            mock.assert_called_once_with("co-1", months_before=6)
        assert result == alerts


# --- MeetingRepository ---


class TestMeetingRepository:
    """MeetingRepository délègue à cse_service_impl."""

    def test_list_by_company_calls_impl(self):
        repo = MeetingRepository()
        meetings = [{"id": "mtg-1", "title": "CSE"}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_meetings",
            return_value=meetings,
        ) as mock:
            result = repo.list_by_company(
                "co-1",
                status="terminee",
                meeting_type="ordinaire",
                participant_id="emp-1",
            )
            mock.assert_called_once_with(
                "co-1",
                status="terminee",
                meeting_type="ordinaire",
                participant_id="emp-1",
            )
        assert result == meetings

    def test_get_by_id_calls_impl(self):
        repo = MeetingRepository()
        meeting = {"id": "mtg-1", "title": "CSE", "company_id": "co-1"}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_meeting_by_id",
            return_value=meeting,
        ) as mock:
            result = repo.get_by_id("mtg-1", "co-1")
            mock.assert_called_once_with("mtg-1", "co-1")
        assert result == meeting

    def test_get_participants_calls_impl(self):
        repo = MeetingRepository()
        participants = [{"employee_id": "emp-1", "role": "participant"}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_meeting_participants",
            return_value=participants,
        ) as mock:
            result = repo.get_participants("mtg-1")
            mock.assert_called_once_with("mtg-1")
        assert result == participants


# --- RecordingRepository ---


class TestRecordingRepository:
    """RecordingRepository : get_status via impl, get_minutes_path via queries."""

    def test_get_status_calls_impl(self):
        repo = RecordingRepository()
        status = {"meeting_id": "mtg-1", "status": "completed"}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_recording_status",
            return_value=status,
        ) as mock:
            result = repo.get_status("mtg-1")
            mock.assert_called_once_with("mtg-1")
        assert result == status

    def test_get_minutes_path_calls_fetch_meeting_minutes_path(self):
        repo = RecordingRepository()
        with patch(
            "app.modules.cse.infrastructure.repository.fetch_meeting_minutes_path",
            return_value="path/to/pv.pdf",
        ) as mock:
            result = repo.get_minutes_path("mtg-1", "co-1")
            mock.assert_called_once_with("mtg-1")
        assert result == "path/to/pv.pdf"

    def test_get_minutes_path_returns_none_when_absent(self):
        repo = RecordingRepository()
        with patch(
            "app.modules.cse.infrastructure.repository.fetch_meeting_minutes_path",
            return_value=None,
        ):
            result = repo.get_minutes_path("mtg-1", "co-1")
        assert result is None


# --- DelegationRepository ---


class TestDelegationRepository:
    """DelegationRepository : get_quota, list_hours, get_summary via impl ; list_quotas via queries + mapper."""

    def test_get_quota_calls_impl(self):
        repo = DelegationRepository()
        quota = {"id": "q-1", "quota_hours_per_month": 10.0}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_delegation_quota",
            return_value=quota,
        ) as mock:
            result = repo.get_quota("co-1", "emp-1")
            mock.assert_called_once_with("co-1", "emp-1")
        assert result == quota

    def test_list_quotas_uses_fetch_and_mapper(self):
        repo = DelegationRepository()
        rows = [
            {
                "id": "q-1",
                "company_id": "co-1",
                "collective_agreement_id": "cc-1",
                "quota_hours_per_month": 10.0,
                "notes": None,
                "collective_agreements_catalog": {"name": "Syntec"},
            },
        ]
        with patch(
            "app.modules.cse.infrastructure.repository.fetch_delegation_quotas_for_company",
            return_value=rows,
        ):
            result = repo.list_quotas("co-1")
        assert len(result) == 1
        assert result[0].id == "q-1"
        assert result[0].quota_hours_per_month == 10.0
        assert result[0].collective_agreement_name == "Syntec"

    def test_list_hours_calls_impl(self):
        repo = DelegationRepository()
        hours = [{"id": "h-1", "duration_hours": 2.0}]
        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_delegation_hours",
            return_value=hours,
        ) as mock:
            result = repo.list_hours("co-1", "emp-1", period_start=start, period_end=end)
            mock.assert_called_once_with("co-1", "emp-1", start, end)
        assert result == hours

    def test_get_summary_calls_impl(self):
        repo = DelegationRepository()
        summary = [{"employee_id": "emp-1", "consumed_hours": 5.0}]
        start = date(2024, 3, 1)
        end = date(2024, 3, 31)
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_delegation_summary",
            return_value=summary,
        ) as mock:
            result = repo.get_summary("co-1", start, end)
            mock.assert_called_once_with("co-1", start, end)
        assert result == summary


# --- BDESDocumentRepository ---


class TestBDESDocumentRepository:
    """BDESDocumentRepository délègue à cse_service_impl."""

    def test_list_by_company_calls_impl(self):
        repo = BDESDocumentRepository()
        docs = [{"id": "doc-1", "title": "BDES 2024"}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_bdes_documents",
            return_value=docs,
        ) as mock:
            result = repo.list_by_company(
                "co-1",
                year=2024,
                document_type="bdes",
                visible_to_elected_only=True,
            )
            mock.assert_called_once_with(
                "co-1",
                year=2024,
                document_type="bdes",
                visible_to_elected_only=True,
            )
        assert result == docs

    def test_get_by_id_calls_impl(self):
        repo = BDESDocumentRepository()
        doc = {"id": "doc-1", "title": "BDES", "company_id": "co-1"}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_bdes_document_by_id",
            return_value=doc,
        ) as mock:
            result = repo.get_by_id("doc-1", "co-1")
            mock.assert_called_once_with("doc-1", "co-1")
        assert result == doc


# --- ElectionCycleRepository ---


class TestElectionCycleRepository:
    """ElectionCycleRepository délègue à cse_service_impl."""

    def test_list_by_company_calls_impl(self):
        repo = ElectionCycleRepository()
        cycles = [{"id": "cycle-1", "cycle_name": "2024-2026"}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_election_cycles",
            return_value=cycles,
        ) as mock:
            result = repo.list_by_company("co-1")
            mock.assert_called_once_with("co-1")
        assert result == cycles

    def test_get_by_id_calls_impl(self):
        repo = ElectionCycleRepository()
        cycle = {"id": "cycle-1", "cycle_name": "2024-2026", "company_id": "co-1"}
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_election_cycle_by_id",
            return_value=cycle,
        ) as mock:
            result = repo.get_by_id("cycle-1", "co-1")
            mock.assert_called_once_with("cycle-1", "co-1")
        assert result == cycle

    def test_get_election_alerts_calls_impl(self):
        repo = ElectionCycleRepository()
        alerts = [{"cycle_id": "cycle-1", "days_remaining": 90, "alert_level": "warning"}]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.get_election_alerts",
            return_value=alerts,
        ) as mock:
            result = repo.get_election_alerts("co-1")
            mock.assert_called_once_with("co-1")
        assert result == alerts
