"""Résolution employé sur les routes /api/annual-reviews/me*."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


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


class TestAnnualReviewsMeResolve:
    def test_get_me_uses_resolved_employee_id(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.annual_reviews.api.router._resolve_employee_id_for_current_user",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.annual_reviews.api.router.queries.get_my_annual_reviews",
                    return_value=[],
                ) as mock_list,
            ):
                response = client.get("/api/annual-reviews/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_list.assert_called_once()
        assert mock_list.call_args[0][0] == TEST_EMPLOYEE_ID

    def test_get_me_empty_when_unlinked(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.annual_reviews.api.router._resolve_employee_id_for_current_user",
                    return_value=None,
                ),
                patch(
                    "app.modules.annual_reviews.api.router.queries.get_my_annual_reviews",
                ) as mock_list,
            ):
                response = client.get("/api/annual-reviews/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json() == []
        mock_list.assert_not_called()

    def test_get_me_current_uses_resolved_employee_id(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.annual_reviews.api.router._resolve_employee_id_for_current_user",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.annual_reviews.api.router.queries.get_my_current_annual_review",
                    return_value=None,
                ) as mock_current,
            ):
                response = client.get("/api/annual-reviews/me/current")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert mock_current.call_args[0][0] == TEST_EMPLOYEE_ID
