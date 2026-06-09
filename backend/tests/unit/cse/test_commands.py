"""
Tests unitaires des commandes CSE (application/commands.py).

Les commandes délèguent à l'infrastructure (cse_service_impl).
On mocke ces appels pour vérifier les paramètres et retours.
"""

from datetime import date
from unittest.mock import patch, MagicMock


from app.modules.cse.application import commands
from app.modules.cse.schemas import ElectedMemberCreate, MeetingCreate, MeetingUpdate


# --- create_elected_member ---


class TestCreateElectedMember:
    """Commande create_elected_member."""

    def test_delegates_to_impl_and_returns_result(self):
        """Délègue à cse_service_impl.create_elected_member et retourne le résultat."""
        data = ElectedMemberCreate(
            employee_id="emp-1",
            role="titulaire",
            start_date=date(2024, 1, 1),
            end_date=date(2026, 12, 31),
        )
        expected = MagicMock()
        expected.id = "mem-new"
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.create_elected_member",
            return_value=expected,
        ) as mock_create:
            result = commands.create_elected_member(
                company_id="co-1",
                data=data,
                created_by="user-1",
            )
        assert result == expected
        mock_create.assert_called_once_with("co-1", data, "user-1")

    def test_works_without_created_by(self):
        """created_by optionnel (None)."""
        data = ElectedMemberCreate(
            employee_id="emp-2",
            role="suppleant",
            start_date=date(2024, 6, 1),
            end_date=date(2025, 5, 31),
        )
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.create_elected_member",
            return_value=MagicMock(),
        ) as mock_create:
            commands.create_elected_member(company_id="co-1", data=data)
        mock_create.assert_called_once_with("co-1", data, None)


# --- update_elected_member ---


class TestUpdateElectedMember:
    """Commande update_elected_member."""

    def test_delegates_to_impl_and_returns_result(self):
        """Délègue à cse_service_impl.update_elected_member."""
        data = MagicMock()
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.update_elected_member",
            return_value=expected,
        ) as mock_update:
            result = commands.update_elected_member(
                member_id="mem-1",
                data=data,
                company_id="co-1",
            )
        assert result == expected
        mock_update.assert_called_once_with("mem-1", data, "co-1")


# --- create_meeting ---


class TestCreateMeeting:
    """Commande create_meeting."""

    def test_delegates_to_impl_and_returns_result(self):
        """Délègue à cse_service_impl.create_meeting."""
        data = MeetingCreate(
            title="CSE ordinaire",
            meeting_date=date(2024, 3, 15),
            meeting_type="ordinaire",
        )
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.create_meeting",
            return_value=expected,
        ) as mock_create:
            result = commands.create_meeting(
                company_id="co-1",
                data=data,
                created_by="user-1",
            )
        assert result == expected
        mock_create.assert_called_once_with("co-1", data, "user-1")


# --- update_meeting ---


class TestUpdateMeeting:
    """Commande update_meeting."""

    def test_delegates_to_impl_and_returns_result(self):
        """Délègue à cse_service_impl.update_meeting."""
        data = MeetingUpdate(status="terminee")
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.update_meeting",
            return_value=expected,
        ) as mock_update:
            result = commands.update_meeting(
                meeting_id="mtg-1",
                company_id="co-1",
                data=data,
            )
        assert result == expected
        mock_update.assert_called_once_with("mtg-1", "co-1", data)


# --- add_participants ---


class TestAddParticipants:
    """Commande add_participants."""

    def test_delegates_to_impl_and_returns_list(self):
        """Délègue à cse_service_impl.add_participants."""
        employee_ids = ["emp-1", "emp-2"]
        expected = [MagicMock(), MagicMock()]
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.add_participants",
            return_value=expected,
        ) as mock_add:
            result = commands.add_participants("mtg-1", employee_ids)
        assert result == expected
        mock_add.assert_called_once_with("mtg-1", employee_ids)


# --- remove_participant ---


class TestRemoveParticipant:
    """Commande remove_participant."""

    def test_delegates_to_impl_returns_none(self):
        """Délègue à cse_service_impl.remove_participant (retourne None)."""
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.remove_participant",
            return_value=None,
        ) as mock_remove:
            result = commands.remove_participant("mtg-1", "emp-1")
        assert result is None
        mock_remove.assert_called_once_with("mtg-1", "emp-1")


class TestUpdateParticipantAttendance:
    """Commande update_participant_attendance."""

    def test_delegates_to_impl(self):
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.update_participant_attendance",
            return_value=expected,
        ) as mock_update:
            result = commands.update_participant_attendance(
                "mtg-1", "emp-1", "co-1", True
            )
        assert result == expected
        mock_update.assert_called_once_with("mtg-1", "emp-1", "co-1", True)


# --- create_delegation_hour ---


class TestCreateDelegationHour:
    """Commande create_delegation_hour."""

    def test_delegates_to_impl(self):
        """Délègue à cse_service_impl.create_delegation_hour."""
        data = MagicMock()
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.create_delegation_hour",
            return_value=expected,
        ) as mock_create:
            result = commands.create_delegation_hour(
                company_id="co-1",
                employee_id="emp-1",
                data=data,
                created_by="user-1",
            )
        assert result == expected
        mock_create.assert_called_once_with("co-1", "emp-1", data, "user-1")


# --- upload_bdes_document ---


class TestUploadBdesDocument:
    """Commande upload_bdes_document."""

    def test_delegates_to_impl(self):
        """Délègue à cse_service_impl.upload_bdes_document."""
        data = MagicMock()
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.upload_bdes_document",
            return_value=expected,
        ) as mock_upload:
            result = commands.upload_bdes_document(
                company_id="co-1",
                data=data,
                published_by="user-1",
            )
        assert result == expected
        mock_upload.assert_called_once_with("co-1", data, "user-1")


# --- create_election_cycle ---


class TestCreateElectionCycle:
    """Commande create_election_cycle."""

    def test_delegates_to_impl(self):
        """Délègue à cse_service_impl.create_election_cycle."""
        data = MagicMock()
        expected = MagicMock()
        with patch(
            "app.modules.cse.infrastructure.cse_service_impl.create_election_cycle",
            return_value=expected,
        ) as mock_create:
            result = commands.create_election_cycle("co-1", data)
        assert result == expected
        mock_create.assert_called_once_with("co-1", data)
