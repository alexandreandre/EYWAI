"""
Tests de câblage (wiring) du module CSE.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application queries/commands -> repository / service) fonctionnent.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "cse-wiring-co"
TEST_USER_ID = "cse-wiring-rh"
TEST_ELECTED_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"


def _rh_user():
    """Utilisateur RH avec active_company_id."""
    return User(
        id=TEST_USER_ID,
        email="rh@cse-wiring.com",
        first_name="RH",
        last_name="Wiring",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="CSE Wiring Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


def _elected_user():
    """Élu CSE (collaborateur) avec active_company_id."""
    return User(
        id="cse-wiring-elected",
        email="elu@cse-wiring.com",
        first_name="Elu",
        last_name="CSE",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="CSE Wiring Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestCSEWiringElectedMembers:
    """Flux GET /api/cse/elected-members : router -> queries -> repository."""

    def test_list_elected_members_flow_uses_repository(self, client: TestClient):
        """Le router appelle queries.get_elected_members qui utilise elected_member_repository."""
        from app.core.security import get_current_user

        mock_members = [
            {
                "id": "mem-1",
                "employee_id": "emp-1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "role": "titulaire",
                "start_date": "2024-01-01",
                "end_date": "2026-12-31",
                "is_active": True,
            },
        ]
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.cse.application.queries.elected_member_repository"
            ) as mock_repo:
                mock_repo.list_by_company.return_value = mock_members
                response = client.get("/api/cse/elected-members")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "mem-1"
        assert data[0]["first_name"] == "Jean"
        mock_repo.list_by_company.assert_called_once_with(
            TEST_COMPANY_ID, active_only=True
        )


class TestCSEWiringMeetings:
    """Flux GET /api/cse/meetings : router -> queries -> meeting_repository."""

    def test_list_meetings_flow_uses_repository(self, client: TestClient):
        """Le router appelle queries.get_meetings qui utilise meeting_repository."""
        from app.core.security import get_current_user

        mock_meetings = [
            {
                "id": "mtg-1",
                "title": "CSE ordinaire",
                "meeting_date": "2024-03-15",
                "meeting_type": "ordinaire",
                "status": "a_venir",
                "participant_count": 5,
                "created_at": "2024-01-01T10:00:00",
            },
        ]
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.cse.application.queries.meeting_repository"
            ) as mock_repo:
                mock_repo.list_by_company.return_value = mock_meetings
                response = client.get("/api/cse/meetings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "mtg-1"
        assert data[0]["title"] == "CSE ordinaire"
        mock_repo.list_by_company.assert_called_once_with(
            TEST_COMPANY_ID,
            status=None,
            meeting_type=None,
            participant_id=None,
        )

    def test_list_meetings_elected_filters_by_participant(self, client: TestClient):
        """Un élu ne voit que les réunions où il est participant."""
        from app.core.security import get_current_user

        elected = _elected_user()
        app.dependency_overrides[get_current_user] = lambda: elected
        try:
            with (
                patch(
                    "app.modules.cse.api.router._resolve_employee_id_for_current_user",
                    return_value=TEST_ELECTED_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.cse.api.router.queries.is_elected_member",
                    return_value=True,
                ),
                patch(
                    "app.modules.cse.application.queries.meeting_repository"
                ) as mock_repo,
            ):
                mock_repo.list_by_company.return_value = []
                response = client.get("/api/cse/meetings")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_repo.list_by_company.assert_called_once_with(
            TEST_COMPANY_ID,
            status=None,
            meeting_type=None,
            participant_id=TEST_ELECTED_EMPLOYEE_ID,
        )


class TestCSEWiringCreateElectedMember:
    """Flux POST /api/cse/elected-members : router -> commands -> cse_service_impl."""

    def test_create_elected_member_flow_calls_command(self, client: TestClient):
        """Le router appelle commands.create_elected_member qui délègue à cse_service_impl."""
        from app.core.security import get_current_user

        created = {
            "id": "mem-new",
            "employee_id": "emp-1",
            "role": "titulaire",
            "company_id": TEST_COMPANY_ID,
            "start_date": "2024-01-01",
            "end_date": "2026-12-31",
            "is_active": True,
            "created_at": "2024-01-15T10:00:00",
            "updated_at": "2024-01-15T10:00:00",
        }
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with patch(
                "app.modules.cse.infrastructure.cse_service_impl.create_elected_member",
                return_value=created,
            ) as mock_create:
                response = client.post(
                    "/api/cse/elected-members",
                    json={
                        "employee_id": "emp-1",
                        "role": "titulaire",
                        "start_date": "2024-01-01",
                        "end_date": "2026-12-31",
                    },
                )
                mock_create.assert_called_once()
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        assert response.json()["id"] == "mem-new"


class TestCSEWiringExportElectedMembers:
    """Flux GET /api/cse/exports/elected-members : router -> service.export_elected_members_file."""

    def test_export_flow_uses_queries_and_provider(self, client: TestClient):
        """Le router appelle export_elected_members_file qui utilise queries + cse_export_provider."""
        from app.core.security import get_current_user

        mock_content = b"xlsx-bytes"
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        try:
            with (
                patch(
                    "app.modules.cse.application.service.queries.get_elected_members",
                    return_value=[],
                ),
                patch(
                    "app.modules.cse.application.service.cse_export_provider.export_elected_members",
                    return_value=mock_content,
                ),
            ):
                response = client.get("/api/cse/exports/elected-members")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.content == mock_content
        assert "base_elus_cse" in response.headers.get("Content-Disposition", "")
