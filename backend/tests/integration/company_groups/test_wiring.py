"""
Tests de câblage (wiring) du module company_groups.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application -> repository / providers) fonctionnent pour ce module.
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


def _super_admin():
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


def _admin_user():
    return User(
        id=TEST_USER_ID,
        email="admin@test.com",
        first_name="Admin",
        last_name="User",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="admin",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestCompanyGroupsWiringMyGroups:
    """Flux GET /api/company-groups/my-groups : router -> queries.get_my_groups -> repository + mappers."""

    def test_my_groups_flow_calls_queries_and_returns_formatted_list(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        user = _super_admin()
        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Mon Groupe"
        dto.siren = None
        dto.description = None
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = datetime.now()
        dto.companies = [
            {"id": TEST_COMPANY_ID, "company_name": "C1", "siret": None, "is_active": True},
        ]
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with patch(
                "app.modules.company_groups.application.queries.get_my_groups",
                return_value=[dto],
            ) as get_my_groups:
                response = client.get("/api/company-groups/my-groups")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200, response.json() if response.status_code != 200 else ""
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == TEST_GROUP_ID
        assert data[0]["group_name"] == "Mon Groupe"
        assert len(data[0]["companies"]) == 1
        assert data[0]["companies"][0]["company_name"] == "C1"
        get_my_groups.assert_called_once()
        call_user = get_my_groups.call_args[0][0]
        assert call_user.is_super_admin is True


class TestCompanyGroupsWiringCreateGroup:
    """Flux POST /api/company-groups/ : router -> commands.create_group -> repository."""

    def test_create_group_flow_calls_command_and_returns_201(self, client: TestClient):
        from app.core.security import get_current_user

        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Nouveau Groupe Wiring"
        dto.siren = "123456789"
        dto.description = None
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = dto.created_at
        with patch(
            "app.modules.company_groups.application.commands.create_group",
            return_value=dto,
        ) as create_group:
            app.dependency_overrides[get_current_user] = lambda: _super_admin()
            try:
                response = client.post(
                    "/api/company-groups/",
                    json={
                        "group_name": "Nouveau Groupe Wiring",
                        "siren": "123456789",
                        "description": None,
                        "logo_url": None,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["group_name"] == "Nouveau Groupe Wiring"
        assert body["id"] == TEST_GROUP_ID
        create_group.assert_called_once()
        call_data = create_group.call_args[0][0]
        assert call_data.group_name == "Nouveau Groupe Wiring"
        assert call_data.siren == "123456789"


class TestCompanyGroupsWiringGetGroupDetails:
    """Flux GET /api/company-groups/{group_id} : router -> queries.get_group_details."""

    def test_get_group_details_flow_calls_query_and_returns_dto(self, client: TestClient):
        from app.core.security import get_current_user

        user = _admin_user()
        dto = MagicMock()
        dto.id = TEST_GROUP_ID
        dto.group_name = "Détail Groupe"
        dto.siren = None
        dto.description = "Description"
        dto.logo_url = None
        dto.is_active = True
        dto.created_at = datetime.now()
        dto.updated_at = datetime.now()
        dto.companies = []
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            with patch(
                "app.modules.company_groups.application.queries.get_group_details",
                return_value=dto,
            ) as get_group_details:
                response = client.get(f"/api/company-groups/{TEST_GROUP_ID}")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200, response.json() if response.status_code != 200 else ""
        assert response.json()["group_name"] == "Détail Groupe"
        get_group_details.assert_called_once()
        assert get_group_details.call_args[0][0] == TEST_GROUP_ID


class TestCompanyGroupsWiringAddCompany:
    """Flux POST add-company : router -> commands.add_company_to_group -> repository."""

    def test_add_company_flow_calls_command_and_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        result = MagicMock()
        result.message = "Entreprise ajoutée au groupe avec succès"
        result.group_id = TEST_GROUP_ID
        result.company_id = TEST_COMPANY_ID
        with patch(
            "app.modules.company_groups.application.commands.add_company_to_group",
            return_value=result,
        ) as add_company:
            app.dependency_overrides[get_current_user] = lambda: _admin_user()
            try:
                response = client.post(
                    f"/api/company-groups/{TEST_GROUP_ID}/add-company/{TEST_COMPANY_ID}",
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        add_company.assert_called_once_with(
            TEST_GROUP_ID, TEST_COMPANY_ID, _admin_user()
        )


class TestCompanyGroupsWiringServiceAndRepository:
    """Vérification que le service utilise bien le repository (get_company_ids_for_group)."""

    def test_get_company_ids_for_group_uses_repository(self):
        """Flux service.get_company_ids_for_group -> repository.get_company_ids_by_group_id."""
        from app.modules.company_groups.application import service as service_module

        mock_repo = MagicMock()
        # Retourner les company_ids accessibles par _admin_user() pour que l'intersection ne soit pas vide
        mock_repo.get_company_ids_by_group_id.return_value = [
            TEST_COMPANY_ID,
            "660e8400-e29b-41d4-a716-446655440002",
        ]
        user = _admin_user()
        # Patcher l'import utilisé par le module service (repository est importé au chargement)
        with patch(
            "app.modules.company_groups.application.service.company_group_repository",
            mock_repo,
        ):
            result = service_module.get_company_ids_for_group(TEST_GROUP_ID, user)

        mock_repo.get_company_ids_by_group_id.assert_called_once_with(TEST_GROUP_ID)
        # L'utilisateur admin a accès à TEST_COMPANY_ID uniquement, donc intersection = [TEST_COMPANY_ID]
        assert result == [TEST_COMPANY_ID]
