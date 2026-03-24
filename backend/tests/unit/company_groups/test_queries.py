"""
Tests unitaires des queries du module company_groups (application/queries.py).

Repository, service et providers mockés : pas d'accès DB ni RPC.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.modules.company_groups.application import queries
from app.modules.company_groups.application.dto import (
    GroupListSummaryDto,
    GroupWithCompaniesDto,
)

MODULE_QUERIES = "app.modules.company_groups.application.queries"


def _make_user(is_super_admin: bool = False, accessible_company_ids=None):
    """Utilisateur mock avec is_super_admin et accessible_companies."""
    user = MagicMock()
    user.is_super_admin = is_super_admin
    if accessible_company_ids is None:
        accessible_company_ids = []
    accs = [MagicMock(company_id=cid) for cid in accessible_company_ids]
    user.accessible_companies = accs
    return user


class TestGetMyGroups:
    """Query get_my_groups."""

    def test_returns_empty_when_user_has_no_accessible_companies(self):
        """Utilisateur non super_admin sans entreprises → liste vide."""
        user = _make_user(is_super_admin=False, accessible_company_ids=[])
        with patch(f"{MODULE_QUERIES}.get_accessible_company_ids", return_value=[]), patch(
            f"{MODULE_QUERIES}.company_group_repository"
        ) as mock_repo:
            result = queries.get_my_groups(user)
        assert result == []
        mock_repo.list_groups_with_companies.assert_not_called()

    def test_returns_groups_for_accessible_companies(self):
        """Liste les groupes contenant au moins une entreprise accessible."""
        user = _make_user(is_super_admin=False, accessible_company_ids=["c1"])
        mock_repo = MagicMock()
        mock_repo.list_groups_with_companies.return_value = [
            {"id": "g1", "group_name": "G1", "companies": [{"id": "c1", "company_name": "C1"}]},
        ]
        aggregated = [
            {
                "id": "g1",
                "group_name": "G1",
                "siren": None,
                "description": None,
                "logo_url": None,
                "is_active": True,
                "created_at": None,
                "updated_at": None,
                "companies": [{"id": "c1", "company_name": "C1", "siret": None, "is_active": True}],
            },
        ]
        with patch(f"{MODULE_QUERIES}.get_accessible_company_ids", return_value=["c1"]), patch(
            f"{MODULE_QUERIES}.company_group_repository", mock_repo
        ), patch(
            f"{MODULE_QUERIES}.rows_to_groups_with_companies", return_value=aggregated
        ):
            result = queries.get_my_groups(user)
        assert len(result) == 1
        assert isinstance(result[0], GroupWithCompaniesDto)
        assert result[0].id == "g1"
        assert result[0].group_name == "G1"
        mock_repo.list_groups_with_companies.assert_called_once_with(["c1"])

    def test_super_admin_gets_all_groups(self):
        """Super admin : company_ids=None → tous les groupes."""
        user = _make_user(is_super_admin=True)
        mock_repo = MagicMock()
        mock_repo.list_groups_with_companies.return_value = []
        with patch(f"{MODULE_QUERIES}.get_accessible_company_ids", return_value=[]), patch(
            f"{MODULE_QUERIES}.company_group_repository", mock_repo
        ), patch(f"{MODULE_QUERIES}.rows_to_groups_with_companies", return_value=[]):
            queries.get_my_groups(user)
        mock_repo.list_groups_with_companies.assert_called_once_with(None)


class TestGetGroupDetails:
    """Query get_group_details."""

    def test_raises_when_group_not_found(self):
        """LookupError si le groupe n'existe pas."""
        mock_repo = MagicMock()
        mock_repo.get_by_id_with_companies.return_value = None
        user = _make_user(is_super_admin=True)
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo):
            with pytest.raises(LookupError, match="Groupe non trouvé"):
                queries.get_group_details("g-inexistant", user)

    def test_raises_permission_when_no_accessible_company_in_group(self):
        """PermissionError si l'utilisateur n'a accès à aucune entreprise du groupe."""
        mock_repo = MagicMock()
        mock_repo.get_by_id_with_companies.return_value = {
            "id": "g1",
            "group_name": "G1",
            "companies": [{"id": "c1"}, {"id": "c2"}],
        }
        user = _make_user(is_super_admin=False, accessible_company_ids=[])
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.get_accessible_company_ids", return_value=[]
        ):
            with pytest.raises(PermissionError, match="aucune entreprise"):
                queries.get_group_details("g1", user)

    def test_returns_dto_for_super_admin(self):
        """Super admin reçoit le groupe complet."""
        row = {
            "id": "g1",
            "group_name": "G1",
            "siren": "123456789",
            "description": "Desc",
            "logo_url": None,
            "is_active": True,
            "created_at": None,
            "updated_at": None,
            "companies": [{"id": "c1", "company_name": "C1", "siret": None, "is_active": True}],
        }
        mock_repo = MagicMock()
        mock_repo.get_by_id_with_companies.return_value = row
        user = _make_user(is_super_admin=True)
        mapped = {**row, "companies": row["companies"]}
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.row_to_group_with_companies", return_value=mapped
        ):
            result = queries.get_group_details("g1", user)
        assert isinstance(result, GroupWithCompaniesDto)
        assert result.id == "g1"
        assert result.group_name == "G1"
        assert result.siren == "123456789"


class TestGetGroupConsolidatedStats:
    """Query get_group_consolidated_stats."""

    def test_raises_when_no_companies_in_group(self):
        """LookupError si aucune entreprise dans le groupe."""
        mock_repo = MagicMock()
        mock_repo.get_companies_for_group_stats.return_value = []
        user = _make_user(is_super_admin=True)
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=[]
        ):
            with pytest.raises(LookupError, match="Aucune entreprise trouvée"):
                queries.get_group_consolidated_stats("g1", user)

    def test_raises_permission_when_no_accessible_company(self):
        """PermissionError si l'utilisateur n'a accès à aucune entreprise."""
        mock_repo = MagicMock()
        mock_repo.get_companies_for_group_stats.return_value = [{"id": "c1"}]
        user = _make_user(is_super_admin=False)
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=[]
        ):
            with pytest.raises(PermissionError, match="aucune entreprise"):
                queries.get_group_consolidated_stats("g1", user)

    def test_returns_provider_result(self):
        """Délègue au provider et retourne son résultat."""
        mock_repo = MagicMock()
        mock_repo.get_companies_for_group_stats.return_value = [{"id": "c1"}]
        user = _make_user(is_super_admin=True)
        dashboard_data = {"total_employees": 10, "payroll": 50000}
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=["c1"]
        ), patch(
            f"{MODULE_QUERIES}.call_get_group_consolidated_dashboard",
            return_value=dashboard_data,
        ):
            result = queries.get_group_consolidated_stats(
                "g1", user, year=2024, month=6
            )
        assert result == dashboard_data


class TestGetGroupEmployeesStats:
    """Query get_group_employees_stats."""

    def test_raises_permission_when_no_accessible_company(self):
        with patch(f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=[]):
            with pytest.raises(PermissionError, match="Aucune entreprise accessible"):
                queries.get_group_employees_stats("g1", _make_user())

    def test_returns_provider_result(self):
        stats = [{"company_id": "c1", "employees_count": 5}]
        with patch(
            f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=["c1"]
        ), patch(
            f"{MODULE_QUERIES}.call_get_group_employees_stats", return_value=stats
        ):
            result = queries.get_group_employees_stats("g1", _make_user())
        assert result == stats


class TestGetGroupPayrollEvolution:
    """Query get_group_payroll_evolution."""

    def test_raises_permission_when_no_accessible_company(self):
        with patch(f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=[]):
            with pytest.raises(PermissionError, match="Aucune entreprise accessible"):
                queries.get_group_payroll_evolution(
                    "g1", _make_user(), 2024, 1, 2024, 12
                )

    def test_returns_provider_result(self):
        evolution = [{"month": 1, "year": 2024, "total": 10000}]
        with patch(
            f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=["c1"]
        ), patch(
            f"{MODULE_QUERIES}.call_get_group_payroll_evolution",
            return_value=evolution,
        ):
            result = queries.get_group_payroll_evolution(
                "g1", _make_user(), 2024, 1, 2024, 12
            )
        assert result == evolution


class TestGetGroupCompanyComparison:
    """Query get_group_company_comparison."""

    def test_raises_permission_when_no_accessible_company(self):
        with patch(f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=[]):
            with pytest.raises(PermissionError, match="Aucune entreprise accessible"):
                queries.get_group_company_comparison(
                    "g1", _make_user(), "employees"
                )

    def test_returns_provider_result(self):
        comparison = [{"company_id": "c1", "value": 10}]
        with patch(
            f"{MODULE_QUERIES}.get_company_ids_for_group", return_value=["c1"]
        ), patch(
            f"{MODULE_QUERIES}.call_get_group_company_comparison",
            return_value=comparison,
        ):
            result = queries.get_group_company_comparison(
                "g1", _make_user(), "payroll", year=2024, month=6
            )
        assert result == comparison


class TestGetAllGroups:
    """Query get_all_groups (super_admin only)."""

    def test_raises_when_not_super_admin(self):
        """PermissionError si l'utilisateur n'est pas super_admin."""
        user = _make_user(is_super_admin=False)
        with pytest.raises(PermissionError, match="super administrateurs"):
            queries.get_all_groups(user)

    def test_returns_list_summary_dtos(self):
        """Retourne liste de GroupListSummaryDto avec company_count et total_employees."""
        user = _make_user(is_super_admin=True)
        mock_repo = MagicMock()
        mock_repo.list_all_active_ordered.return_value = [
            {"id": "g1", "group_name": "G1", "description": None, "created_at": None},
        ]
        mock_repo.get_groups_with_company_and_effectif.return_value = [
            {
                "id": "g1",
                "group_name": "G1",
                "description": None,
                "created_at": None,
                "company_count": 2,
                "total_employees": 15,
            },
        ]
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo):
            result = queries.get_all_groups(user)
        assert len(result) == 1
        assert isinstance(result[0], GroupListSummaryDto)
        assert result[0].company_count == 2
        assert result[0].total_employees == 15


class TestGetGroupCompanies:
    """Query get_group_companies (super_admin only)."""

    def test_raises_when_not_super_admin(self):
        user = _make_user(is_super_admin=False)
        with pytest.raises(PermissionError, match="super administrateurs"):
            queries.get_group_companies("g1", user)

    def test_returns_repository_companies(self):
        user = _make_user(is_super_admin=True)
        companies = [{"id": "c1", "company_name": "C1", "siret": "123"}]
        mock_repo = MagicMock()
        mock_repo.get_companies_by_group_id.return_value = companies
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo):
            result = queries.get_group_companies("g1", user)
        assert result == companies
        mock_repo.get_companies_by_group_id.assert_called_once_with("g1")


class TestGetAvailableCompanies:
    """Query get_available_companies (super_admin only)."""

    def test_raises_when_not_super_admin(self):
        user = _make_user(is_super_admin=False)
        with pytest.raises(PermissionError, match="super administrateurs"):
            queries.get_available_companies(user)

    def test_returns_companies_without_group(self):
        user = _make_user(is_super_admin=True)
        companies = [{"id": "c1", "company_name": "Sans groupe"}]
        mock_repo = MagicMock()
        mock_repo.get_companies_without_group.return_value = companies
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo):
            result = queries.get_available_companies(user)
        assert result == companies


class TestGetGroupUserAccesses:
    """Query get_group_user_accesses (super_admin only)."""

    def test_raises_when_not_super_admin(self):
        user = _make_user(is_super_admin=False)
        with pytest.raises(PermissionError, match="super administrateurs"):
            queries.get_group_user_accesses("g1", user)

    def test_returns_empty_when_no_companies_in_group(self):
        user = _make_user(is_super_admin=True)
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = []
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo):
            result = queries.get_group_user_accesses("g1", user)
        assert result == []

    def test_returns_accesses_with_emails(self):
        user = _make_user(is_super_admin=True)
        mock_repo = MagicMock()
        mock_repo.get_company_ids_by_group_id.return_value = ["c1"]
        mock_repo.get_user_accesses_for_companies.return_value = [
            {
                "user_id": "u1",
                "company_id": "c1",
                "role": "admin",
                "profiles": {"first_name": "Jean", "last_name": "Dupont"},
                "companies": {"company_name": "C1"},
            },
        ]
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.CompanyGroupRepository.get_user_emails_map",
            return_value={"u1": "jean@test.com"},
        ):
            result = queries.get_group_user_accesses("g1", user)
        assert len(result) == 1
        assert result[0]["user_id"] == "u1"
        assert result[0]["email"] == "jean@test.com"
        assert result[0]["role"] == "admin"
        assert result[0]["company_name"] == "C1"


class TestGetDetailedUserAccesses:
    """Query get_detailed_user_accesses (super_admin only)."""

    def test_raises_when_not_super_admin(self):
        user = _make_user(is_super_admin=False)
        with pytest.raises(PermissionError, match="super administrateurs"):
            queries.get_detailed_user_accesses("g1", user)

    def test_returns_companies_and_users_structure(self):
        user = _make_user(is_super_admin=True)
        mock_repo = MagicMock()
        mock_repo.get_companies_by_group_id.return_value = [
            {"id": "c1", "company_name": "C1", "siret": None},
        ]
        mock_repo.get_detailed_accesses_for_companies.return_value = [
            {
                "user_id": "u1",
                "company_id": "c1",
                "role": "admin",
                "is_primary": True,
                "profiles": {"first_name": "Jean", "last_name": "Dupont"},
            },
        ]
        with patch(f"{MODULE_QUERIES}.company_group_repository", mock_repo), patch(
            f"{MODULE_QUERIES}.CompanyGroupRepository.get_user_emails_map",
            return_value={"u1": "jean@test.com"},
        ):
            result = queries.get_detailed_user_accesses("g1", user)
        assert "companies" in result
        assert "users" in result
        assert len(result["companies"]) == 1
        assert len(result["users"]) == 1
        assert result["users"][0]["user_id"] == "u1"
        assert result["users"][0]["accesses"]["c1"]["role"] == "admin"
        assert result["users"][0]["accesses"]["c1"]["is_primary"] is True
