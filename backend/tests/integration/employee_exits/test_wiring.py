"""
Tests de câblage (wiring) du module employee_exits.

Vérifient que l'injection des dépendances et le flux de bout en bout sont corrects :
router monté, get_current_user utilisé, commands/queries appelés avec les bons paramètres.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-wiring-test"
TEST_USER_ID = "user-wiring-test"
EXIT_ID = "exit-wiring-uuid"


def _make_rh_user():
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_USER_ID,
        email="rh@test.com",
        first_name="RH",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


class TestEmployeeExitsRouterMounted:
    """Vérification que le router employee_exits est monté sous /api/employee-exits."""

    def test_route_prefix_returns_401_without_auth(self, client: TestClient):
        """GET /api/employee-exits exige une authentification (401 sans token)."""
        response = client.get("/api/employee-exits")
        assert response.status_code == 401

    def test_route_prefix_accepts_authenticated_request(self, client: TestClient):
        """Avec get_current_user overridé, GET /api/employee-exits appelle list_employee_exits avec company_id."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
                mock_queries.list_employee_exits.return_value = []
                response = client.get("/api/employee-exits")
            assert response.status_code == 200
            mock_queries.list_employee_exits.assert_called_once()
            # Premier argument = company_id (injecté depuis current_user.active_company_id)
            assert mock_queries.list_employee_exits.call_args[0][0] == TEST_COMPANY_ID
        finally:
            app.dependency_overrides.pop(get_current_user, None)


class TestEmployeeExitsFlowEndToEnd:
    """Flux bout en bout : commande appelée depuis la route avec les bons paramètres."""

    def test_get_exit_calls_query_with_exit_id_and_company_id(self, client: TestClient):
        """GET /api/employee-exits/{id} appelle get_employee_exit(exit_id, company_id)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
                mock_queries.get_employee_exit.return_value = {
                    "id": EXIT_ID,
                    "company_id": TEST_COMPANY_ID,
                    "employee_id": "emp-1",
                    "exit_type": "demission",
                    "status": "demission_recue",
                    "documents": [],
                    "checklist_items": [],
                    "checklist_completion_rate": 0.0,
                }
                response = client.get(f"/api/employee-exits/{EXIT_ID}")
            assert response.status_code == 200
            mock_queries.get_employee_exit.assert_called_once_with(
                EXIT_ID, TEST_COMPANY_ID
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_delete_exit_calls_command_with_exit_id_and_company_id(
        self, client: TestClient
    ):
        """DELETE /api/employee-exits/{id} appelle delete_employee_exit(exit_id, company_id)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.employee_exits.api.router.commands"
            ) as mock_commands:
                response = client.delete(f"/api/employee-exits/{EXIT_ID}")
            assert response.status_code == 204
            mock_commands.delete_employee_exit.assert_called_once_with(
                EXIT_ID, TEST_COMPANY_ID
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
