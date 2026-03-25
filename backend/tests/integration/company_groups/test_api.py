"""
Tests d'intégration HTTP des routes du module company_groups.

Routes : GET /api/company-groups/my-groups, GET/POST/PATCH /api/company-groups/,
GET /api/company-groups/{id}, GET .../consolidated-stats, employees-stats,
payroll-evolution, company-comparison, companies, available-companies,
user-accesses, detailed-user-accesses ; POST add-company, bulk companies,
manage-user-access ; DELETE remove-company, user-access.
Utilise : client (TestClient), dependency_overrides pour get_current_user,
et mocks pour queries/commands (pas de DB ni JWT réels).

Fixture documentée : company_groups_headers — pour tests E2E avec token réel,
ajouter dans conftest.py une fixture company_groups_headers (ou auth_headers) pour
un utilisateur super_admin ou admin de plusieurs entreprises, avec format
{\"Authorization\": \"Bearer <jwt>\"}. Optionnel : \"X-Active-Company\": \"<company_id>\".
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess

pytestmark = pytest.mark.integration

TEST_GROUP_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_COMPANY_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_USER_ID = "770e8400-e29b-41d4-a716-446655440002"


def _make_super_admin():
    """Utilisateur super admin."""
    return User(
        id=TEST_USER_ID,
        email="super@test.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _make_admin_user(company_ids=None):
    """Utilisateur admin des entreprises données."""
    if company_ids is None:
        company_ids = [TEST_COMPANY_ID]
    accesses = [
        CompanyAccess(
            company_id=cid,
            company_name=f"Company {cid[:8]}",
            role="admin",
            is_primary=(i == 0),
        )
        for i, cid in enumerate(company_ids)
    ]
    return User(
        id=TEST_USER_ID,
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=accesses,
        active_company_id=company_ids[0] if company_ids else None,
    )


def _make_rh_user(company_id=TEST_COMPANY_ID):
    """Utilisateur RH (non admin) sur une entreprise."""
    return User(
        id=TEST_USER_ID,
        email="rh@test.com",
        first_name="RH",
        last_name="User",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


class TestCompanyGroupsUnauthenticated:
    """Sans token : 401 sur les routes protégées."""

    def test_get_my_groups_returns_401(self, client: TestClient):
        response = client.get("/api/company-groups/my-groups")
        assert response.status_code == 401

    def test_get_all_groups_returns_401(self, client: TestClient):
        response = client.get("/api/company-groups/")
        assert response.status_code == 401

    def test_get_group_details_returns_401(self, client: TestClient):
        response = client.get(f"/api/company-groups/{TEST_GROUP_ID}")
        assert response.status_code == 401

    def test_post_create_group_returns_401(self, client: TestClient):
        response = client.post(
            "/api/company-groups/",
            json={
                "group_name": "Groupe",
                "siren": None,
                "description": None,
                "logo_url": None,
            },
        )
        assert response.status_code == 401


class TestGetMyGroups:
    """GET /api/company-groups/my-groups."""

    def test_returns_200_with_mock_queries(self, client: TestClient):
        from app.core.security import get_current_user

        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Groupe Test"
        dto.siren = None
        dto.description = None
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = datetime.now()
        dto.companies = []
        with patch(
            "app.modules.company_groups.application.queries.get_my_groups",
            return_value=[dto],
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.get("/api/company-groups/my-groups")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == TEST_GROUP_ID
        assert data[0]["group_name"] == "Groupe Test"


class TestGetAllGroups:
    """GET /api/company-groups/ (super_admin only)."""

    def test_non_super_admin_returns_403(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
        try:
            response = client.get("/api/company-groups/")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_super_admin_returns_200_with_mock(self, client: TestClient):
        from app.core.security import get_current_user

        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "G1"
        dto.description = "Desc"
        dto.created_at = None
        dto.company_count = 2
        dto.total_employees = 10
        with patch(
            "app.modules.company_groups.application.queries.get_all_groups",
            return_value=[dto],
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.get("/api/company-groups/")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["company_count"] == 2
        assert data[0]["total_employees"] == 10


class TestGetGroupDetails:
    """GET /api/company-groups/{group_id}."""

    def test_returns_404_when_group_not_found(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.company_groups.application.queries.get_group_details",
            side_effect=LookupError("Groupe non trouvé"),
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.get(f"/api/company-groups/{TEST_GROUP_ID}")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404
        assert "Groupe" in response.json().get("detail", "")

    def test_returns_200_with_mock(self, client: TestClient):
        from app.core.security import get_current_user

        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Groupe"
        dto.siren = "123456789"
        dto.description = None
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = datetime.now()
        dto.companies = [
            {
                "id": TEST_COMPANY_ID,
                "company_name": "C1",
                "siret": None,
                "is_active": True,
            }
        ]
        with patch(
            "app.modules.company_groups.application.queries.get_group_details",
            return_value=dto,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.get(f"/api/company-groups/{TEST_GROUP_ID}")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["group_name"] == "Groupe"
        assert response.json()["siren"] == "123456789"


class TestCreateGroup:
    """POST /api/company-groups/."""

    def test_returns_403_when_not_admin_of_at_least_two_companies(
        self, client: TestClient
    ):
        """Utilisateur non super_admin et admin d'une seule entreprise → 403."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_admin_user(
            [TEST_COMPANY_ID]
        )
        try:
            response = client.post(
                "/api/company-groups/",
                json={
                    "group_name": "Groupe",
                    "siren": None,
                    "description": None,
                    "logo_url": None,
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "2 entreprises" in response.json().get("detail", "")

    def test_returns_201_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Nouveau Groupe"
        dto.siren = "123456789"
        dto.description = None
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = dto.created_at
        with patch(
            "app.modules.company_groups.application.commands.create_group",
            return_value=dto,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.post(
                    "/api/company-groups/",
                    json={
                        "group_name": "Nouveau Groupe",
                        "siren": "123456789",
                        "description": None,
                        "logo_url": None,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        assert response.json()["group_name"] == "Nouveau Groupe"
        assert response.json()["id"] == TEST_GROUP_ID


class TestUpdateGroup:
    """PATCH /api/company-groups/{group_id}."""

    def test_returns_200_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Groupe Mis à Jour"
        dto.siren = None
        dto.description = "Nouvelle desc"
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = datetime.now()
        with (
            patch(
                "app.modules.company_groups.application.commands.update_group",
                return_value=dto,
            ),
            patch(
                "app.modules.company_groups.api.router.get_group_company_ids_for_permission_check",
                return_value=[TEST_COMPANY_ID],
            ),
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_admin_user(
                [TEST_COMPANY_ID]
            )
            try:
                response = client.patch(
                    f"/api/company-groups/{TEST_GROUP_ID}",
                    json={
                        "group_name": "Groupe Mis à Jour",
                        "siren": None,
                        "description": "Nouvelle desc",
                        "logo_url": None,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["group_name"] == "Groupe Mis à Jour"


class TestAddCompanyToGroup:
    """POST /api/company-groups/{group_id}/add-company/{company_id}."""

    def test_returns_403_when_not_admin_of_company(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.post(
                f"/api/company-groups/{TEST_GROUP_ID}/add-company/{TEST_COMPANY_ID}",
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_returns_200_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        result = MagicMock()
        result.message = "Entreprise ajoutée au groupe avec succès"
        result.group_id = TEST_GROUP_ID
        result.company_id = TEST_COMPANY_ID
        with patch(
            "app.modules.company_groups.application.commands.add_company_to_group",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
            try:
                response = client.post(
                    f"/api/company-groups/{TEST_GROUP_ID}/add-company/{TEST_COMPANY_ID}",
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["company_id"] == TEST_COMPANY_ID


class TestRemoveCompanyFromGroup:
    """DELETE /api/company-groups/{group_id}/remove-company/{company_id}."""

    def test_returns_200_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        result = MagicMock()
        result.message = "Entreprise retirée du groupe avec succès"
        result.company_id = TEST_COMPANY_ID
        result.group_id = None
        with patch(
            "app.modules.company_groups.application.commands.remove_company_from_group",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
            try:
                response = client.delete(
                    f"/api/company-groups/{TEST_GROUP_ID}/remove-company/{TEST_COMPANY_ID}",
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["company_id"] == TEST_COMPANY_ID


class TestBulkAddCompaniesToGroup:
    """POST /api/company-groups/{group_id}/companies/bulk."""

    def test_returns_400_when_company_ids_empty(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
        try:
            response = client.post(
                f"/api/company-groups/{TEST_GROUP_ID}/companies/bulk",
                json={"company_ids": []},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 400

    def test_returns_200_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        result = MagicMock()
        result.message = "2 entreprise(s) ajoutée(s) au groupe"
        result.success_count = 2
        result.failed_count = 0
        result.failed_companies = []
        with patch(
            "app.modules.company_groups.application.commands.bulk_add_companies_to_group",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.post(
                    f"/api/company-groups/{TEST_GROUP_ID}/companies/bulk",
                    json={"company_ids": [TEST_COMPANY_ID, "another-id"]},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["success_count"] == 2


class TestManageUserAccessInGroup:
    """POST /api/company-groups/{group_id}/manage-user-access (super_admin only)."""

    def test_returns_403_when_not_super_admin(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
        try:
            response = client.post(
                f"/api/company-groups/{TEST_GROUP_ID}/manage-user-access",
                json={
                    "user_email": "user@test.com",
                    "accesses": [{"company_id": TEST_COMPANY_ID, "role": "admin"}],
                    "first_name": None,
                    "last_name": None,
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_returns_200_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        result = MagicMock()
        result.message = "Accès utilisateur mis à jour avec succès"
        result.user_id = TEST_USER_ID
        result.user_email = "user@test.com"
        result.added_count = 1
        result.updated_count = 0
        result.removed_count = 0
        with patch(
            "app.modules.company_groups.application.commands.manage_user_access_in_group",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.post(
                    f"/api/company-groups/{TEST_GROUP_ID}/manage-user-access",
                    json={
                        "user_email": "user@test.com",
                        "accesses": [{"company_id": TEST_COMPANY_ID, "role": "admin"}],
                        "first_name": None,
                        "last_name": None,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["user_email"] == "user@test.com"
        assert response.json()["added_count"] == 1


class TestRemoveUserFromGroup:
    """DELETE /api/company-groups/{group_id}/user-access/{user_id} (super_admin only)."""

    def test_returns_403_when_not_super_admin(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_admin_user()
        try:
            response = client.delete(
                f"/api/company-groups/{TEST_GROUP_ID}/user-access/{TEST_USER_ID}",
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_returns_200_with_mock_command(self, client: TestClient):
        from app.core.security import get_current_user

        result = MagicMock()
        result.message = "2 accès supprimé(s) pour l'utilisateur"
        result.removed_count = 2
        with patch(
            "app.modules.company_groups.application.commands.remove_user_from_group",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.delete(
                    f"/api/company-groups/{TEST_GROUP_ID}/user-access/{TEST_USER_ID}",
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["removed_count"] == 2


class TestStatsAndComparisonRoutes:
    """GET consolidated-stats, employees-stats, payroll-evolution, company-comparison."""

    def test_consolidated_stats_returns_403_when_no_access(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.company_groups.application.queries.get_group_consolidated_stats",
            side_effect=PermissionError(
                "Vous n'avez accès à aucune entreprise de ce groupe"
            ),
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_admin_user([])
            try:
                response = client.get(
                    f"/api/company-groups/{TEST_GROUP_ID}/consolidated-stats",
                    params={"year": 2024, "month": 6},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_company_comparison_returns_200_with_mock(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.company_groups.application.queries.get_group_company_comparison",
            return_value=[{"company_id": TEST_COMPANY_ID, "value": 10}],
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_super_admin()
            try:
                response = client.get(
                    f"/api/company-groups/{TEST_GROUP_ID}/company-comparison",
                    params={"metric": "employees", "year": 2024, "month": 6},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["company_id"] == TEST_COMPANY_ID
