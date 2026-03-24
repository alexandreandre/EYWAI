"""
Tests de câblage (wiring) du module employees : injection et flux bout en bout.

Vérifie que les dépendances sont correctement résolues et que le flux
application -> repository / providers fonctionne pour ce module.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application import commands, queries
from app.modules.employees.domain.rules import build_employee_folder_name
from app.modules.employees.infrastructure.mappers import prepare_employee_insert_data
from app.modules.employees.infrastructure.repository import (
    EmployeeRepository,
    ProfileRepository,
)


pytestmark = pytest.mark.integration


class TestEmployeesModuleWiring:
    """Vérification que le module employees est correctement câblé."""

    def test_employee_repository_implements_interface(self):
        """EmployeeRepository expose get_by_company, get_by_id, create, update, delete."""
        repo = EmployeeRepository()
        assert hasattr(repo, "get_by_company")
        assert hasattr(repo, "get_by_id")
        assert hasattr(repo, "get_by_id_only")
        assert hasattr(repo, "create")
        assert hasattr(repo, "update")
        assert hasattr(repo, "delete")

    def test_profile_repository_implements_upsert(self):
        """ProfileRepository expose upsert."""
        repo = ProfileRepository()
        assert hasattr(repo, "upsert")

    def test_domain_rules_used_by_mappers(self):
        """build_employee_folder_name produit un nom utilisé par prepare_employee_insert_data."""
        folder_name = build_employee_folder_name("DUPONT", "Jean")
        assert folder_name == "DUPONT_Jean"
        data = prepare_employee_insert_data(
            {"first_name": "Jean", "last_name": "Dupont"},
            new_user_id="u1",
            company_id="c1",
            username="jean.dupont",
            folder_name=folder_name,
        )
        assert data["employee_folder_name"] == "DUPONT_Jean"
        assert data["id"] == "u1"
        assert data["company_id"] == "c1"
        assert data["username"] == "jean.dupont"

    @patch("app.modules.employees.application.queries._employee_repository")
    def test_get_employees_flow_uses_repository(self, mock_repo):
        """get_employees délègue au repository et enrichit les lignes."""
        mock_repo.get_by_company.return_value = [
            {"id": "e1", "first_name": "Jean", "company_id": "c1"},
        ]
        result = queries.get_employees("c1")
        mock_repo.get_by_company.assert_called_once_with("c1")
        assert len(result) == 1
        assert result[0]["id"] == "e1"

    @patch("app.modules.employees.application.commands._employee_repository")
    @patch("app.modules.employees.application.commands.get_auth_provider")
    def test_update_employee_flow_uses_repository(
        self, mock_get_auth, mock_repo
    ):
        """update_employee délègue au repository et retourne les données mises à jour."""
        mock_repo.get_by_id_only.return_value = {
            "id": "e1",
            "company_id": "c1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "coordonnees_bancaires": {},
        }
        mock_repo.update.return_value = {
            "id": "e1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "phone_number": "+33600000000",
        }
        result = commands.update_employee("e1", {"phone_number": "+33600000000"})
        mock_repo.update.assert_called_once()
        assert result["phone_number"] == "+33600000000"
