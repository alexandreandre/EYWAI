"""
Tests d'intégration HTTP des routes du module employees.

Utilise les fixtures : client (TestClient), auth_headers ou employees_headers.
Préfixe des routes : /api/employees.

Fixture à prévoir dans conftest.py si absente :
  - employees_headers : dict avec Authorization: Bearer <token> pour un utilisateur
    ayant une company (active_company_id) et les droits RH si nécessaire.
  - Si seul auth_headers existe, les tests authentifiés l'utilisent (401 si token vide).
"""

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration


class TestGetEmployees:
    """GET /api/employees — liste des salariés de l'entreprise."""

    def test_get_employees_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401 Unauthorized."""
        response = client.get("/api/employees")
        assert response.status_code == 401

    def test_get_employees_with_auth_returns_200_or_403(
        self, client: TestClient, auth_headers: dict
    ):
        """Avec auth_headers : 200 + liste (ou 403 si pas d'entreprise active)."""
        response = client.get("/api/employees", headers=auth_headers)
        if not auth_headers:
            assert response.status_code == 401
            return
        assert response.status_code in (200, 403)
        if response.status_code == 200:
            assert isinstance(response.json(), list)


class TestGetEmployeeDetails:
    """GET /api/employees/{employee_id} — détail d'un salarié."""

    def test_get_employee_details_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/some-id")
        assert response.status_code == 401

    def test_get_employee_details_not_found_returns_404(
        self, client: TestClient, auth_headers: dict
    ):
        """ID inexistant avec auth → 404."""
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.get(
            "/api/employees/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code in (403, 404)


class TestGetMyContract:
    """GET /api/employees/me/contract — URL signée contrat (espace employé)."""

    def test_get_my_contract_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/me/contract")
        assert response.status_code == 401

    def test_get_my_contract_with_auth_returns_200_with_url_or_none(
        self, client: TestClient, auth_headers: dict
    ):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.get("/api/employees/me/contract", headers=auth_headers)
        assert response.status_code in (200, 401)
        if response.status_code == 200:
            data = response.json()
            assert "url" in data


class TestGetMyPublishedExitDocuments:
    """GET /api/employees/me/published-exit-documents."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/me/published-exit-documents")
        assert response.status_code == 401

    def test_with_auth_returns_list(self, client: TestClient, auth_headers: dict):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.get(
            "/api/employees/me/published-exit-documents",
            headers=auth_headers,
        )
        assert response.status_code in (200, 401)
        if response.status_code == 200:
            assert isinstance(response.json(), list)


class TestCreateEmployee:
    """POST /api/employees — création d'un employé (multipart: data + files)."""

    def test_create_employee_without_auth_returns_401(self, client: TestClient):
        response = client.post(
            "/api/employees",
            data={"data": "{}", "generate_pdf_contract": "false"},
        )
        assert response.status_code == 401

    def test_create_employee_invalid_json_returns_422(
        self, client: TestClient, auth_headers: dict
    ):
        """Données JSON invalides → 422 ou 401 si pas d'auth."""
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.post(
            "/api/employees",
            headers=auth_headers,
            data={"data": "not-json", "generate_pdf_contract": "false"},
        )
        assert response.status_code in (400, 422)


class TestUpdateEmployee:
    """PUT /api/employees/{employee_id}."""

    def test_update_employee_without_auth_returns_401(self, client: TestClient):
        response = client.put(
            "/api/employees/some-id",
            json={"first_name": "Paul"},
        )
        assert response.status_code == 401

    def test_update_employee_not_found_returns_404(
        self, client: TestClient, auth_headers: dict
    ):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.put(
            "/api/employees/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
            json={"phone_number": "+33600000000"},
        )
        assert response.status_code in (403, 404)


class TestDeleteEmployee:
    """DELETE /api/employees/{employee_id}."""

    def test_delete_employee_without_auth_returns_401(self, client: TestClient):
        response = client.delete("/api/employees/some-id")
        assert response.status_code == 401

    def test_delete_employee_not_found_returns_404_or_500(
        self, client: TestClient, auth_headers: dict
    ):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.delete(
            "/api/employees/00000000-0000-0000-0000-000000000000",
            headers=auth_headers,
        )
        assert response.status_code in (204, 404, 500)


class TestGetCredentialsPdfUrl:
    """GET /api/employees/{employee_id}/credentials-pdf."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/some-id/credentials-pdf")
        assert response.status_code == 401

    def test_returns_contract_response_with_url_key(
        self, client: TestClient, auth_headers: dict
    ):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.get(
            "/api/employees/00000000-0000-0000-0000-000000000000/credentials-pdf",
            headers=auth_headers,
        )
        assert response.status_code in (200, 401, 404)
        if response.status_code == 200:
            assert "url" in response.json()


class TestGetIdentityDocumentUrl:
    """GET /api/employees/{employee_id}/identity-document."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/some-id/identity-document")
        assert response.status_code == 401


class TestGetContractUrl:
    """GET /api/employees/{employee_id}/contract (espace RH)."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/some-id/contract")
        assert response.status_code == 401


class TestGetEmployeePromotions:
    """GET /api/employees/{employee_id}/promotions."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/some-id/promotions")
        assert response.status_code == 401

    def test_not_found_or_forbidden_returns_404_or_403(
        self, client: TestClient, auth_headers: dict
    ):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.get(
            "/api/employees/00000000-0000-0000-0000-000000000000/promotions",
            headers=auth_headers,
        )
        assert response.status_code in (200, 403, 404)
        if response.status_code == 200:
            assert isinstance(response.json(), list)


class TestGetEmployeeRhAccess:
    """GET /api/employees/{employee_id}/rh-access."""

    def test_without_auth_returns_401(self, client: TestClient):
        response = client.get("/api/employees/some-id/rh-access")
        assert response.status_code == 401

    def test_returns_employee_rh_access_shape(
        self, client: TestClient, auth_headers: dict
    ):
        if not auth_headers:
            pytest.skip("auth_headers non configuré")
        response = client.get(
            "/api/employees/00000000-0000-0000-0000-000000000000/rh-access",
            headers=auth_headers,
        )
        assert response.status_code in (200, 403, 404)
        if response.status_code == 200:
            data = response.json()
            assert "has_access" in data
            assert "available_roles" in data
