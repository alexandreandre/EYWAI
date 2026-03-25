"""
Tests d'intégration HTTP des routes du module access_control.

Utilise les fixtures : client (TestClient), auth_headers (conftest.py).
Préfixe des routes : /api/access-control.

Documentation fixture : pour des tests avec utilisateur authentifié ayant accès RH,
ajouter dans conftest.py une fixture access_control_headers (ou utiliser auth_headers
avec un token valide pour un utilisateur ayant au moins un accès RH à une entreprise).
"""

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestAccessControlPermissionCategories:
    """GET /api/access-control/permission-categories."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token Bearer → 401 (require_rh_access)."""
        response = client.get("/api/access-control/permission-categories")
        assert response.status_code == 401

    def test_with_auth_returns_200_or_403(self, client: TestClient, auth_headers: dict):
        """Avec auth_headers : 200 si token valide et accès RH, 403 sinon."""
        response = client.get(
            "/api/access-control/permission-categories",
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403)
            if response.status_code == 200:
                assert isinstance(response.json(), list)
        else:
            assert response.status_code == 401


class TestAccessControlPermissionActions:
    """GET /api/access-control/permission-actions."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/access-control/permission-actions")
        assert response.status_code == 401

    def test_with_auth_returns_200_or_403(self, client: TestClient, auth_headers: dict):
        """Avec auth_headers : 200 ou 403 selon droits."""
        response = client.get(
            "/api/access-control/permission-actions",
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403)
            if response.status_code == 200:
                assert isinstance(response.json(), list)
        else:
            assert response.status_code == 401


class TestAccessControlPermissions:
    """GET /api/access-control/permissions."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/access-control/permissions")
        assert response.status_code == 401

    def test_with_auth_and_optional_filters(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 200/403 ; filtres category_id, required_role en query."""
        response = client.get(
            "/api/access-control/permissions",
            params={"category_id": "cat-1", "required_role": "rh"},
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403)
            if response.status_code == 200:
                assert isinstance(response.json(), list)
        else:
            assert response.status_code == 401


class TestAccessControlPermissionsMatrix:
    """GET /api/access-control/permissions/matrix."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401 (get_current_user)."""
        response = client.get(
            "/api/access-control/permissions/matrix",
            params={"company_id": "00000000-0000-0000-0000-000000000001"},
        )
        assert response.status_code == 401

    def test_with_auth_requires_company_id(
        self, client: TestClient, auth_headers: dict
    ):
        """company_id requis ; avec auth → 200/403/422."""
        response = client.get(
            "/api/access-control/permissions/matrix",
            params={"company_id": "00000000-0000-0000-0000-000000000001"},
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403)
            if response.status_code == 200:
                data = response.json()
                assert "categories" in data
        else:
            assert response.status_code == 401


class TestAccessControlUserPermissions:
    """GET /api/access-control/users/{user_id}/permissions."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/access-control/users/00000000-0000-0000-0000-000000000001/permissions",
            params={"company_id": "00000000-0000-0000-0000-000000000002"},
        )
        assert response.status_code == 401

    def test_with_auth_returns_200_403_or_404(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 200 (résumé), 403 (pas droit), 404 (user sans accès company)."""
        response = client.get(
            "/api/access-control/users/00000000-0000-0000-0000-000000000001/permissions",
            params={"company_id": "00000000-0000-0000-0000-000000000002"},
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403, 404)
            if response.status_code == 200:
                data = response.json()
                assert "user_id" in data
                assert "company_id" in data
                assert "base_role" in data
        else:
            assert response.status_code == 401


class TestAccessControlRoleTemplates:
    """GET /api/access-control/role-templates."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/access-control/role-templates")
        assert response.status_code == 401

    def test_with_auth_and_filters(self, client: TestClient, auth_headers: dict):
        """Avec auth ; query params : company_id, base_role, include_system."""
        response = client.get(
            "/api/access-control/role-templates",
            params={
                "company_id": "00000000-0000-0000-0000-000000000001",
                "include_system": "true",
            },
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403)
            if response.status_code == 200:
                assert isinstance(response.json(), list)
        else:
            assert response.status_code == 401


class TestAccessControlRoleTemplateQuickCreate:
    """POST /api/access-control/role-templates/quick-create."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/access-control/role-templates/quick-create",
            json={
                "name": "Template Test",
                "job_title": "RH",
                "base_role": "rh",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert response.status_code == 401

    def test_with_auth_valid_payload_returns_201_or_403_400(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth et body valide : 201 créé, 403 pas RH, 400 nom dupliqué."""
        response = client.post(
            "/api/access-control/role-templates/quick-create",
            headers=auth_headers,
            json={
                "name": "Template Test QuickCreate",
                "job_title": "Responsable",
                "base_role": "rh",
                "company_id": "00000000-0000-0000-0000-000000000001",
                "description": "Description test",
                "permission_ids": [],
            },
        )
        if auth_headers:
            assert response.status_code in (201, 400, 403)
            if response.status_code == 201:
                data = response.json()
                assert "message" in data
                assert "template_id" in data
                assert "name" in data
        else:
            assert response.status_code == 401

    def test_without_required_fields_returns_422(
        self, client: TestClient, auth_headers: dict
    ):
        """Body sans name ou company_id → 422."""
        if not auth_headers:
            pytest.skip("Need auth to hit validation")
        response = client.post(
            "/api/access-control/role-templates/quick-create",
            headers=auth_headers,
            json={"job_title": "RH", "base_role": "rh"},
        )
        assert response.status_code == 422


class TestAccessControlRoleTemplateById:
    """GET /api/access-control/role-templates/{template_id}."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/access-control/role-templates/00000000-0000-0000-0000-000000000001",
        )
        assert response.status_code == 401

    def test_with_auth_returns_200_403_or_404(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 200 (détail template + permissions), 403, 404 si inconnu."""
        response = client.get(
            "/api/access-control/role-templates/00000000-0000-0000-0000-000000000001",
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403, 404)
            if response.status_code == 200:
                data = response.json()
                assert "id" in data
                assert "name" in data
                assert "permissions" in data
        else:
            assert response.status_code == 401


class TestAccessControlCheckHierarchy:
    """GET /api/access-control/check-hierarchy."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/access-control/check-hierarchy",
            params={
                "target_role": "rh",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert response.status_code == 401

    def test_with_auth_returns_200_with_is_allowed(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth : 200 et is_allowed, creator_role, target_role, message."""
        response = client.get(
            "/api/access-control/check-hierarchy",
            params={
                "target_role": "rh",
                "company_id": "00000000-0000-0000-0000-000000000001",
            },
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code == 200
            data = response.json()
            assert "is_allowed" in data
            assert "creator_role" in data
            assert data["target_role"] == "rh"
            assert "message" in data
        else:
            assert response.status_code == 401


class TestAccessControlCheckPermission:
    """GET /api/access-control/check-permission."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get(
            "/api/access-control/check-permission",
            params={
                "user_id": "00000000-0000-0000-0000-000000000001",
                "company_id": "00000000-0000-0000-0000-000000000002",
                "permission_code": "payslips.create",
            },
        )
        assert response.status_code == 401

    def test_with_auth_returns_200_or_403(self, client: TestClient, auth_headers: dict):
        """Avec auth : 200 (has_permission, permission_code, user_id, company_id) ou 403."""
        response = client.get(
            "/api/access-control/check-permission",
            params={
                "user_id": "00000000-0000-0000-0000-000000000001",
                "company_id": "00000000-0000-0000-0000-000000000002",
                "permission_code": "payslips.create",
            },
            headers=auth_headers,
        )
        if auth_headers:
            assert response.status_code in (200, 403)
            if response.status_code == 200:
                data = response.json()
                assert "has_permission" in data
                assert data["permission_code"] == "payslips.create"
        else:
            assert response.status_code == 401
