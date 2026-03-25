"""
Tests unitaires des commandes du module company_groups (application/commands.py).

Repository et user lookup mockés : pas d'accès DB ni Auth.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.modules.company_groups.application import commands
from app.modules.company_groups.application.dto import (
    AddRemoveCompanyResultDto,
    BulkAddCompaniesResultDto,
    CompanyGroupDto,
    ManageUserAccessResultDto,
    RemoveUserFromGroupResultDto,
)

MODULE_COMMANDS = "app.modules.company_groups.application.commands"


def _make_create_data(**kwargs):
    """Objet type CompanyGroupCreate (attributs group_name, siren, description, logo_url)."""
    d = MagicMock()
    d.group_name = kwargs.get("group_name", "Groupe Test")
    d.siren = kwargs.get("siren")
    d.description = kwargs.get("description")
    d.logo_url = kwargs.get("logo_url")
    return d


def _make_manage_request(
    user_email: str, accesses: list, first_name=None, last_name=None
):
    """Objet type ManageUserAccessRequest."""
    r = MagicMock()
    r.user_email = user_email
    r.accesses = accesses
    r.first_name = first_name
    r.last_name = last_name
    return r


class TestCreateGroup:
    """Commande create_group."""

    def test_create_group_returns_dto(self):
        """Crée un groupe et retourne CompanyGroupDto."""
        mock_repo = MagicMock()
        now = datetime.now()
        mock_repo.create.return_value = {
            "id": "g-new",
            "group_name": "Nouveau Groupe",
            "siren": "123456789",
            "description": None,
            "logo_url": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        data = _make_create_data(group_name="Nouveau Groupe", siren="123456789")

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.create_group(data, current_user=MagicMock())

        assert isinstance(result, CompanyGroupDto)
        assert result.id == "g-new"
        assert result.group_name == "Nouveau Groupe"
        assert result.siren == "123456789"
        mock_repo.create.assert_called_once()
        payload = mock_repo.create.call_args[0][0]
        assert payload["group_name"] == "Nouveau Groupe"
        assert payload["siren"] == "123456789"
        assert payload["is_active"] is True

    def test_create_group_raises_when_repo_returns_none(self):
        """RuntimeError si le repository retourne None."""
        mock_repo = MagicMock()
        mock_repo.create.return_value = None
        data = _make_create_data(group_name="Groupe")

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(RuntimeError, match="Erreur lors de la création"):
                commands.create_group(data, current_user=MagicMock())


class TestUpdateGroup:
    """Commande update_group."""

    def test_update_group_returns_dto(self):
        """Met à jour un groupe et retourne CompanyGroupDto."""
        mock_repo = MagicMock()
        now = datetime.now()
        mock_repo.update.return_value = {
            "id": "g-1",
            "group_name": "Groupe Mis à Jour",
            "siren": None,
            "description": "Desc",
            "logo_url": None,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }
        data = _make_create_data(group_name="Groupe Mis à Jour", description="Desc")

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.update_group("g-1", data, current_user=MagicMock())

        assert isinstance(result, CompanyGroupDto)
        assert result.id == "g-1"
        assert result.group_name == "Groupe Mis à Jour"
        mock_repo.update.assert_called_once_with(
            "g-1", mock_repo.update.call_args[0][1]
        )

    def test_update_group_raises_when_not_found(self):
        """LookupError si le groupe n'existe pas."""
        mock_repo = MagicMock()
        mock_repo.update.return_value = None
        data = _make_create_data(group_name="Groupe")

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(LookupError, match="Groupe non trouvé"):
                commands.update_group("g-inexistant", data, current_user=MagicMock())


class TestAddCompanyToGroup:
    """Commande add_company_to_group."""

    def test_add_company_returns_result_dto(self):
        """Ajoute une entreprise au groupe et retourne AddRemoveCompanyResultDto."""
        mock_repo = MagicMock()
        mock_repo.exists.return_value = True
        mock_repo.set_company_group.return_value = True

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.add_company_to_group(
                "g-1", "c-1", current_user=MagicMock()
            )

        assert isinstance(result, AddRemoveCompanyResultDto)
        assert result.message == "Entreprise ajoutée au groupe avec succès"
        assert result.group_id == "g-1"
        assert result.company_id == "c-1"
        mock_repo.exists.assert_called_once_with("g-1")
        mock_repo.set_company_group.assert_called_once_with("c-1", "g-1")

    def test_add_company_raises_when_group_not_found(self):
        """LookupError si le groupe n'existe pas."""
        mock_repo = MagicMock()
        mock_repo.exists.return_value = False

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(LookupError, match="Groupe non trouvé"):
                commands.add_company_to_group("g-1", "c-1", current_user=MagicMock())
        mock_repo.set_company_group.assert_not_called()

    def test_add_company_raises_when_company_not_found(self):
        """LookupError si set_company_group retourne False."""
        mock_repo = MagicMock()
        mock_repo.exists.return_value = True
        mock_repo.set_company_group.return_value = False

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(LookupError, match="Entreprise non trouvée"):
                commands.add_company_to_group("g-1", "c-1", current_user=MagicMock())


class TestRemoveCompanyFromGroup:
    """Commande remove_company_from_group."""

    def test_remove_company_returns_result_dto(self):
        """Retire une entreprise du groupe."""
        mock_repo = MagicMock()
        mock_repo.set_company_group_with_current.return_value = True

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.remove_company_from_group(
                "g-1", "c-1", current_user=MagicMock()
            )

        assert isinstance(result, AddRemoveCompanyResultDto)
        assert "retirée" in result.message
        assert result.company_id == "c-1"
        mock_repo.set_company_group_with_current.assert_called_once_with(
            "c-1", None, "g-1"
        )

    def test_remove_company_raises_when_company_not_in_group(self):
        """LookupError si l'entreprise n'était pas dans ce groupe."""
        mock_repo = MagicMock()
        mock_repo.set_company_group_with_current.return_value = False

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(LookupError, match="pas dans ce groupe"):
                commands.remove_company_from_group(
                    "g-1", "c-1", current_user=MagicMock()
                )


class TestBulkAddCompaniesToGroup:
    """Commande bulk_add_companies_to_group."""

    def test_bulk_add_returns_result_with_counts(self):
        """Ajoute plusieurs entreprises et retourne succès / échecs."""
        mock_repo = MagicMock()
        mock_repo.exists.return_value = True
        mock_repo.set_company_group.side_effect = [
            True,
            False,
            True,
        ]  # c1 ok, c2 ko, c3 ok

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.bulk_add_companies_to_group(
                "g-1", ["c1", "c2", "c3"], current_user=MagicMock()
            )

        assert isinstance(result, BulkAddCompaniesResultDto)
        assert result.success_count == 2
        assert result.failed_count == 1
        assert "c2" in result.failed_companies
        assert "2 entreprise(s) ajoutée(s)" in result.message

    def test_bulk_add_raises_when_group_not_found(self):
        """LookupError si le groupe n'existe pas."""
        mock_repo = MagicMock()
        mock_repo.exists.return_value = False

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(LookupError, match="Groupe non trouvé"):
                commands.bulk_add_companies_to_group(
                    "g-1", ["c1", "c2"], current_user=MagicMock()
                )
        mock_repo.set_company_group.assert_not_called()

    def test_bulk_add_exception_on_company_appends_to_failed(self):
        """Si set_company_group lève une exception, la company est ajoutée à failed_companies."""
        mock_repo = MagicMock()
        mock_repo.exists.return_value = True
        mock_repo.set_company_group.side_effect = [True, Exception("DB error"), True]

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.bulk_add_companies_to_group(
                "g-1", ["c1", "c2", "c3"], current_user=MagicMock()
            )

        assert result.success_count == 2
        assert result.failed_count == 1
        assert "c2" in result.failed_companies


class TestManageUserAccessInGroup:
    """Commande manage_user_access_in_group."""

    def test_manage_user_access_raises_when_no_accesses(self):
        """ValueError si request.accesses est vide."""
        request = _make_manage_request("user@test.com", [])
        with pytest.raises(ValueError, match="Au moins un accès"):
            commands.manage_user_access_in_group(
                "g-1", request, current_user=MagicMock()
            )

    def test_manage_user_access_raises_when_company_not_in_group(self):
        """ValueError si une company des accès n'appartient pas au groupe."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1"]
        acc = MagicMock()
        acc.company_id = "c2"
        acc.role = "admin"
        request = _make_manage_request("user@test.com", [acc])

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            with pytest.raises(ValueError, match="n'appartient pas à ce groupe"):
                commands.manage_user_access_in_group(
                    "g-1", request, current_user=MagicMock()
                )

    def test_manage_user_access_raises_when_user_not_found(self):
        """LookupError si l'utilisateur (email) n'existe pas."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1"]
        acc = MagicMock()
        acc.company_id = "c1"
        acc.role = "admin"
        request = _make_manage_request("inconnu@test.com", [acc])

        with (
            patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo),
            patch(
                f"{MODULE_COMMANDS}.CompanyGroupRepository.get_user_by_email",
                return_value=None,
            ),
        ):
            with pytest.raises(LookupError, match="Utilisateur.*non trouvé"):
                commands.manage_user_access_in_group(
                    "g-1", request, current_user=MagicMock()
                )

    def test_manage_user_access_adds_and_removes_returns_dto(self):
        """Ajoute/ met à jour / supprime des accès et retourne ManageUserAccessResultDto."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1", "c2"]
        mock_repo.get_existing_user_accesses.return_value = {"c1": "rh"}
        mock_repo.count_user_accesses.return_value = 1
        acc1 = MagicMock()
        acc1.company_id = "c1"
        acc1.role = "admin"
        acc2 = MagicMock()
        acc2.company_id = "c2"
        acc2.role = "rh"
        request = _make_manage_request("user@test.com", [acc1, acc2])

        with (
            patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo),
            patch(
                f"{MODULE_COMMANDS}.CompanyGroupRepository.get_user_by_email",
                return_value={"id": "u-1", "email": "user@test.com"},
            ),
        ):
            result = commands.manage_user_access_in_group(
                "g-1", request, current_user=MagicMock()
            )

        assert isinstance(result, ManageUserAccessResultDto)
        assert result.user_id == "u-1"
        assert result.user_email == "user@test.com"
        assert result.added_count == 1
        assert result.updated_count == 1
        assert result.removed_count == 0
        mock_repo.update_user_company_access_role.assert_called()
        mock_repo.insert_user_company_access.assert_called()


class TestRemoveUserFromGroup:
    """Commande remove_user_from_group."""

    def test_remove_user_returns_dto_with_removed_count(self):
        """Retire tous les accès de l'utilisateur aux entreprises du groupe."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1", "c2"]
        mock_repo.delete_user_company_accesses.return_value = 2

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.remove_user_from_group(
                "g-1", "u-1", current_user=MagicMock()
            )

        assert isinstance(result, RemoveUserFromGroupResultDto)
        assert result.removed_count == 2
        assert "2 accès supprimé(s)" in result.message
        mock_repo.delete_user_company_accesses.assert_called_once_with(
            "u-1", ["c1", "c2"]
        )

    def test_remove_user_when_group_has_no_companies_returns_zero(self):
        """Si le groupe n'a aucune entreprise, removed_count = 0."""
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = []

        with patch(f"{MODULE_COMMANDS}.company_group_repository", mock_repo):
            result = commands.remove_user_from_group(
                "g-1", "u-1", current_user=MagicMock()
            )

        assert result.removed_count == 0
        assert "Aucune entreprise" in result.message
        mock_repo.delete_user_company_accesses.assert_not_called()
