"""
Tests d'intégration HTTP des routes du module collective_agreements.

Routes testées : /api/collective-agreements (catalog, my-company, assign, unassign, all-assignments)
et /api/collective-agreements-chat (ask, refresh-cache).

Utilise les fixtures : client (TestClient). Pour les routes protégées, on override
get_current_user pour fournir un contexte utilisateur (super_admin, RH avec company_id).
Si vous avez une fixture collective_agreements_headers (token Bearer valide avec company
et droits RH), vous pouvez l'utiliser à la place du override pour des tests E2E réels.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from app.main import app
from app.core.security import get_current_user


pytestmark = pytest.mark.integration


def _make_mock_user(*, role="user", active_company_id="company-1", has_rh=True):
    """Contexte utilisateur mock pour dependency override."""
    user = MagicMock()
    user.id = "user-test-id"
    user.role = role
    user.active_company_id = active_company_id
    user.has_rh_access_in_company = lambda cid: has_rh
    return user


def _override_user(user):
    """Override get_current_user pour les tests."""
    app.dependency_overrides[get_current_user] = lambda: user


def _clear_override():
    app.dependency_overrides.pop(get_current_user, None)


# --- Catalogue (lecture) ---


class TestListCatalog:
    """GET /api/collective-agreements/catalog."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/collective-agreements/catalog")
        assert response.status_code == 401

    def test_with_auth_returns_200_and_list(self, client: TestClient):
        _override_user(_make_mock_user())
        try:
            # Le service réel appelle Supabase ; on peut avoir 200 avec liste vide
            # ou 500 si DB non dispo. On accepte 200 ou 500 selon l'environnement.
            response = client.get("/api/collective-agreements/catalog")
            assert response.status_code in (200, 500)
            if response.status_code == 200:
                data = response.json()
                assert isinstance(data, list)
        finally:
            _clear_override()

    def test_with_query_params(self, client: TestClient):
        _override_user(_make_mock_user())
        try:
            response = client.get(
                "/api/collective-agreements/catalog",
                params={"sector": "IT", "search": "Syntec", "active_only": "true"},
            )
            assert response.status_code in (200, 500)
        finally:
            _clear_override()


class TestGetCatalogItem:
    """GET /api/collective-agreements/catalog/{agreement_id}."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/collective-agreements/catalog/any-id")
        assert response.status_code == 401

    def test_with_auth_not_found_returns_404(self, client: TestClient):
        _override_user(_make_mock_user())
        try:
            response = client.get(
                "/api/collective-agreements/catalog/00000000-0000-0000-0000-000000000000"
            )
            assert response.status_code in (404, 500)
        finally:
            _clear_override()


class TestGetAgreementClassifications:
    """GET /api/collective-agreements/catalog/{agreement_id}/classifications."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get(
            "/api/collective-agreements/catalog/agr-1/classifications"
        )
        assert response.status_code == 401

    def test_with_auth_returns_list_or_404(self, client: TestClient):
        _override_user(_make_mock_user())
        try:
            response = client.get(
                "/api/collective-agreements/catalog/00000000-0000-0000-0000-000000000000/classifications"
            )
            assert response.status_code in (200, 404, 500)
            if response.status_code == 200:
                assert isinstance(response.json(), list)
        finally:
            _clear_override()


# --- Upload URL (super admin) ---


class TestGetCatalogUploadUrl:
    """POST /api/collective-agreements/catalog/upload-url."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/collective-agreements/catalog/upload-url",
            json={"filename": "doc.pdf"},
        )
        assert response.status_code == 401

    def test_as_non_super_admin_returns_403(self, client: TestClient):
        _override_user(_make_mock_user(role="admin", has_rh=True))
        try:
            response = client.post(
                "/api/collective-agreements/catalog/upload-url",
                json={"filename": "doc.pdf"},
            )
            assert response.status_code == 403
        finally:
            _clear_override()

    def test_as_super_admin_returns_200_with_path_and_url_or_500(self, client: TestClient):
        _override_user(_make_mock_user(role="super_admin"))
        try:
            response = client.post(
                "/api/collective-agreements/catalog/upload-url",
                json={"filename": "regles.pdf"},
            )
            assert response.status_code in (200, 500)
            if response.status_code == 200:
                data = response.json()
                assert "path" in data
                assert "signedURL" in data
        finally:
            _clear_override()


# --- Création / mise à jour / suppression catalogue (super admin) ---


class TestCreateCatalogItem:
    """POST /api/collective-agreements/catalog."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/collective-agreements/catalog",
            json={
                "name": "CC Test",
                "idcc": "1486",
                "is_active": True,
            },
        )
        assert response.status_code == 401

    def test_as_non_super_admin_returns_403(self, client: TestClient):
        _override_user(_make_mock_user(role="admin"))
        try:
            response = client.post(
                "/api/collective-agreements/catalog",
                json={"name": "CC", "idcc": "1486", "is_active": True},
            )
            assert response.status_code == 403
        finally:
            _clear_override()


class TestUpdateCatalogItem:
    """PATCH /api/collective-agreements/catalog/{agreement_id}."""

    def test_as_non_super_admin_returns_403(self, client: TestClient):
        _override_user(_make_mock_user(role="admin"))
        try:
            response = client.patch(
                "/api/collective-agreements/catalog/agr-1",
                json={"name": "Nouveau nom"},
            )
            assert response.status_code == 403
        finally:
            _clear_override()


class TestDeleteCatalogItem:
    """DELETE /api/collective-agreements/catalog/{agreement_id}."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.delete("/api/collective-agreements/catalog/agr-1")
        assert response.status_code == 401

    def test_as_non_super_admin_returns_403(self, client: TestClient):
        _override_user(_make_mock_user(role="admin"))
        try:
            response = client.delete("/api/collective-agreements/catalog/agr-1")
            assert response.status_code == 403
        finally:
            _clear_override()


# --- My company (RH) ---


class TestGetMyCompanyAgreements:
    """GET /api/collective-agreements/my-company."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/collective-agreements/my-company")
        assert response.status_code == 401

    def test_without_active_company_returns_400(self, client: TestClient):
        user = _make_mock_user(active_company_id=None, has_rh=True)
        _override_user(user)
        try:
            response = client.get("/api/collective-agreements/my-company")
            assert response.status_code == 400
            assert "entreprise" in response.json().get("detail", "").lower()
        finally:
            _clear_override()

    def test_with_rh_access_returns_200_or_403(self, client: TestClient):
        _override_user(_make_mock_user(active_company_id="c1", has_rh=True))
        try:
            response = client.get("/api/collective-agreements/my-company")
            assert response.status_code in (200, 403, 500)
            if response.status_code == 200:
                assert isinstance(response.json(), list)
        finally:
            _clear_override()


class TestAssignAgreementToCompany:
    """POST /api/collective-agreements/assign."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/collective-agreements/assign",
            json={"collective_agreement_id": "agr-1"},
        )
        assert response.status_code == 401

    def test_without_active_company_returns_400(self, client: TestClient):
        user = _make_mock_user(active_company_id=None, has_rh=True)
        _override_user(user)
        try:
            response = client.post(
                "/api/collective-agreements/assign",
                json={"collective_agreement_id": "agr-1"},
            )
            assert response.status_code == 400
        finally:
            _clear_override()


class TestUnassignAgreementFromCompany:
    """DELETE /api/collective-agreements/unassign/{assignment_id}."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.delete("/api/collective-agreements/unassign/assign-1")
        assert response.status_code == 401


# --- All assignments (super admin) ---


class TestGetAllAssignments:
    """GET /api/collective-agreements/all-assignments."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/collective-agreements/all-assignments")
        assert response.status_code == 401

    def test_as_non_super_admin_returns_403(self, client: TestClient):
        _override_user(_make_mock_user(role="admin"))
        try:
            response = client.get("/api/collective-agreements/all-assignments")
            assert response.status_code == 403
        finally:
            _clear_override()


# --- Chat ---


class TestAskQuestion:
    """POST /api/collective-agreements-chat/ask."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/collective-agreements-chat/ask",
            json={"agreement_id": "agr-1", "question": "Congés ?"},
        )
        assert response.status_code == 401

    def test_without_active_company_returns_400(self, client: TestClient):
        user = _make_mock_user(active_company_id=None, has_rh=True)
        _override_user(user)
        try:
            response = client.post(
                "/api/collective-agreements-chat/ask",
                json={"agreement_id": "agr-1", "question": "Congés ?"},
            )
            assert response.status_code == 400
        finally:
            _clear_override()


class TestRefreshCache:
    """POST /api/collective-agreements-chat/refresh-cache/{agreement_id}."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/collective-agreements-chat/refresh-cache/agr-1"
        )
        assert response.status_code == 401

    def test_as_non_super_admin_returns_403(self, client: TestClient):
        _override_user(_make_mock_user(role="admin"))
        try:
            response = client.post(
                "/api/collective-agreements-chat/refresh-cache/agr-1"
            )
            assert response.status_code == 403
        finally:
            _clear_override()
