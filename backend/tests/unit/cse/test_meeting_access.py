"""Contrôle d'accès détail réunion CSE pour les élus (participant requis)."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
PREFIX = "/api/cse"


def _collaborator_user() -> User:
    return User(
        id=TEST_USER_ID,
        email="emp@test.com",
        first_name="Emp",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestMeetingAccessForElected:
    def test_get_meeting_403_when_not_participant(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.cse.api.router._scoped_employee_id_for_current_user",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.cse.api.router.queries.check_module_active",
                ),
                patch(
                    "app.modules.cse.api.router.queries.is_elected_member",
                    return_value=True,
                ),
                patch(
                    "app.modules.cse.api.router.queries.is_meeting_participant",
                    return_value=False,
                ),
                patch(
                    "app.modules.cse.api.router.queries.get_meeting_by_id",
                ) as mock_get,
            ):
                response = client.get(f"{PREFIX}/meetings/mtg-other")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403
        assert "participant" in response.json()["detail"].lower()
        mock_get.assert_not_called()

    def test_get_meeting_200_when_participant(self, client: TestClient):
        meeting = {
            "id": "mtg-1",
            "company_id": TEST_COMPANY_ID,
            "title": "CSE",
            "meeting_date": "2024-03-15",
            "meeting_time": None,
            "location": None,
            "meeting_type": "ordinaire",
            "status": "a_venir",
            "agenda": None,
            "notes": None,
            "convocations_pdf_path": None,
            "created_by": None,
            "created_at": "2024-01-01T10:00:00",
            "updated_at": "2024-01-01T10:00:00",
        }
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.cse.api.router._scoped_employee_id_for_current_user",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.cse.api.router.queries.check_module_active",
                ),
                patch(
                    "app.modules.cse.api.router.queries.is_elected_member",
                    return_value=True,
                ),
                patch(
                    "app.modules.cse.api.router.queries.is_meeting_participant",
                    return_value=True,
                ),
                patch(
                    "app.modules.cse.api.router.queries.get_meeting_by_id",
                    return_value=meeting,
                ) as mock_get,
            ):
                response = client.get(f"{PREFIX}/meetings/mtg-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_get.assert_called_once_with("mtg-1", TEST_COMPANY_ID)
