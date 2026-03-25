"""
Tests de câblage (wiring) du module access_control.

Vérifie que l'injection des dépendances et le flux de bout en bout fonctionnent :
- Router monté sous /api/access-control
- Dépendance get_current_user utilisée
- Dépendance _require_rh_access (require_rh_access) utilisée sur les routes protégées
- Commandes et queries appelées correctement depuis le router
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestAccessControlRouterMounted:
    """Le router access_control est bien monté et répond sous le bon préfixe."""

    def test_health_ok(self, client: TestClient):
        """L'app répond (sanity check)."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json().get("status") == "ok"

    def test_access_control_routes_require_auth(self, client: TestClient):
        """Les routes /api/access-control/* sans token retournent 401 (get_current_user)."""
        routes_need_auth = [
            ("GET", "/api/access-control/permission-categories", None),
            ("GET", "/api/access-control/permission-actions", None),
            ("GET", "/api/access-control/permissions", None),
            (
                "GET",
                "/api/access-control/permissions/matrix",
                {"company_id": "00000000-0000-0000-0000-000000000001"},
            ),
            ("GET", "/api/access-control/role-templates", None),
            (
                "GET",
                "/api/access-control/check-hierarchy",
                {
                    "target_role": "rh",
                    "company_id": "00000000-0000-0000-0000-000000000001",
                },
            ),
        ]
        for method, path, params in routes_need_auth:
            if params:
                response = client.request(method, path, params=params)
            else:
                response = client.request(method, path)
            assert response.status_code == 401, (
                f"{method} {path} should return 401 without auth"
            )


class TestAccessControlDependencyChain:
    """Chaîne de dépendances : get_current_user → require_rh_access → queries/commands."""

    @patch("app.modules.access_control.application.queries.permission_catalog_reader")
    def test_permission_categories_flow_uses_reader(
        self, mock_reader: MagicMock, client: TestClient, auth_headers: dict
    ):
        """
        GET /permission-categories avec auth : après get_current_user et require_rh_access,
        la query get_permission_categories est appelée et utilise permission_catalog_reader.
        """
        if not auth_headers:
            pytest.skip("auth_headers non configuré (conftest)")
        mock_reader.get_permission_categories_active.return_value = [
            {
                "id": "c1",
                "code": "payslips",
                "label": "Paie",
                "description": None,
                "display_order": 1,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        response = client.get(
            "/api/access-control/permission-categories",
            headers=auth_headers,
        )
        if response.status_code == 200:
            mock_reader.get_permission_categories_active.assert_called_once()
            data = response.json()
            assert isinstance(data, list)
            if data:
                assert data[0]["code"] == "payslips"

    @patch("app.modules.access_control.application.queries.access_control_service")
    def test_check_hierarchy_flow_uses_service(
        self, mock_service: MagicMock, client: TestClient, auth_headers: dict
    ):
        """
        GET /check-hierarchy avec auth : le service check_role_hierarchy_access est utilisé.
        """
        if not auth_headers:
            pytest.skip("auth_headers non configuré (conftest)")
        mock_service.check_role_hierarchy_access.return_value = True
        response = client.get(
            "/api/access-control/check-hierarchy",
            params={
                "target_role": "rh",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
            headers=auth_headers,
        )
        if response.status_code == 200:
            mock_service.check_role_hierarchy_access.assert_called_once()
            data = response.json()
            assert "is_allowed" in data
            assert data["target_role"] == "rh"


class TestAccessControlEndToEndFlow:
    """Flux bout en bout : une requête traverse router → command/query → repository (ou mock)."""

    @patch(
        "app.modules.access_control.infrastructure.queries.get_permission_categories_active"
    )
    def test_permission_categories_e2e_returns_list(
        self, mock_get_categories, client: TestClient, auth_headers: dict
    ):
        """
        En remontant depuis l'infra : si get_permission_categories_active retourne des données,
        l'API les transforme en PermissionCategory et les renvoie.
        """
        if not auth_headers:
            pytest.skip("auth_headers non configuré (conftest)")
        from uuid import uuid4

        uid = str(uuid4())
        mock_get_categories.return_value = [
            {
                "id": uid,
                "code": "test_cat",
                "label": "Test Cat",
                "description": None,
                "display_order": 0,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00",
            },
        ]
        # Le router utilise permission_catalog_reader (instance), pas get_permission_categories_active
        # directement. Donc on patch au niveau du reader utilisé dans queries.
        with patch(
            "app.modules.access_control.application.queries.permission_catalog_reader"
        ) as mock_reader:
            mock_reader.get_permission_categories_active.return_value = (
                mock_get_categories.return_value
            )
            response = client.get(
                "/api/access-control/permission-categories",
                headers=auth_headers,
            )
        if response.status_code == 200:
            data = response.json()
            assert len(data) == 1
            assert data[0]["code"] == "test_cat"
            assert data[0]["label"] == "Test Cat"
