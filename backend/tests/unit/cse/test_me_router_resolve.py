"""Résolution employé sur les routes CSE collaborateur (/elected-members/me, délégation)."""

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


class TestCseMeResolve:
    def test_get_my_elected_status_uses_resolved_employee_id(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.cse.api.router._resolve_employee_id_for_current_user",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.cse.api.router.queries.check_module_active",
                ),
                patch(
                    "app.modules.cse.api.router.queries.get_my_elected_status",
                    return_value={
                        "is_elected": True,
                        "current_mandate": None,
                        "role": "titulaire",
                    },
                ) as mock_status,
            ):
                response = client.get(f"{PREFIX}/elected-members/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_status.assert_called_once_with(TEST_COMPANY_ID, TEST_EMPLOYEE_ID)

    def test_get_my_elected_status_not_elected_when_unlinked(
        self, client: TestClient
    ):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.cse.api.router._resolve_employee_id_for_current_user",
                    return_value=None,
                ),
                patch(
                    "app.modules.cse.api.router.queries.check_module_active",
                ),
                patch(
                    "app.modules.cse.api.router.queries.get_my_elected_status",
                ) as mock_status,
            ):
                response = client.get(f"{PREFIX}/elected-members/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json() == {
            "is_elected": False,
            "current_mandate": None,
            "role": None,
        }
        mock_status.assert_not_called()

    def test_get_delegation_quota_uses_resolved_employee_id(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.cse.api.router._scoped_employee_id_for_current_user",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.cse.api.router._require_elected_or_rh",
                ),
                patch(
                    "app.modules.cse.api.router.queries.check_module_active",
                ),
                patch(
                    "app.modules.cse.api.router.queries.get_delegation_quota",
                    return_value=None,
                ) as mock_quota,
            ):
                response = client.get(f"{PREFIX}/delegation/quota")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_quota.assert_called_once_with(TEST_COMPANY_ID, TEST_EMPLOYEE_ID)
