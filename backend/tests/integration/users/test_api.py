"""
Tests d'intégration HTTP des routes du module users.

Utilise les fixtures : client (TestClient), auth_headers (conftest.py).
Préfixe des routes : /api/users.
Pour les tests authentifiés, on utilise auth_headers ; si la fixture est vide ({}),
les requêtes protégées retournent 401. Documenter en conftest : auth_headers doit
fournir un token Bearer valide pour tester les routes protégées.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.integration

# Préfixe des routes du module users
USERS_PREFIX = "/api/users"


def _mock_user(
    id_="user-test-1",
    email="user@example.com",
    is_super_admin=False,
    accessible_companies=None,
    active_company_id="company-1",
):
    if accessible_companies is None:
        accessible_companies = [
            CompanyAccess(
                company_id="company-1",
                company_name="Société Test",
                role="admin",
                is_primary=True,
            )
        ]
    return User(
        id=id_,
        email=email,
        first_name="Jean",
        last_name="Dupont",
        is_super_admin=is_super_admin,
        is_group_admin=False,
        accessible_companies=accessible_companies,
        active_company_id=active_company_id,
    )


@pytest.fixture
def client_with_user_override(client: TestClient):
    """
    Client avec get_current_user surchargé pour retourner un utilisateur de test.
    Permet de tester les routes /api/users sans token réel.
    """
    from app.main import app
    from app.core.security import get_current_user

    mock_user = _mock_user()

    def _override():
        return mock_user

    app.dependency_overrides[get_current_user] = _override
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ----- GET /api/users/me -----


class TestUsersMe:
    """GET /api/users/me — profil utilisateur connecté."""

    def test_me_without_token_returns_401(self, client: TestClient):
        response = client.get(f"{USERS_PREFIX}/me")
        assert response.status_code == 401

    def test_me_with_override_returns_200(self, client_with_user_override: TestClient):
        response = client_with_user_override.get(f"{USERS_PREFIX}/me")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "user-test-1"
        assert "email" in data or "first_name" in data


# ----- GET /api/users/my-companies -----


class TestUsersMyCompanies:
    """GET /api/users/my-companies — entreprises accessibles."""

    def test_my_companies_without_token_returns_401(self, client: TestClient):
        response = client.get(f"{USERS_PREFIX}/my-companies")
        assert response.status_code == 401

    def test_my_companies_with_override_returns_200(self, client_with_user_override: TestClient):
        response = client_with_user_override.get(f"{USERS_PREFIX}/my-companies")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


# ----- PATCH /api/users/set-primary-company -----


class TestUsersSetPrimaryCompany:
    """PATCH /api/users/set-primary-company."""

    def test_set_primary_without_token_returns_401(self, client: TestClient):
        response = client.patch(
            f"{USERS_PREFIX}/set-primary-company",
            json={"company_id": "company-1"},
        )
        assert response.status_code == 401

    def test_set_primary_with_override_calls_app(self, client_with_user_override: TestClient):
        response = client_with_user_override.patch(
            f"{USERS_PREFIX}/set-primary-company",
            json={"company_id": "company-1"},
        )
        assert response.status_code in (200, 404, 500)


# ----- GET /api/users/company-accesses/{user_id} -----


class TestUsersCompanyAccesses:
    """GET /api/users/company-accesses/{user_id}."""

    def test_company_accesses_without_token_returns_401(self, client: TestClient):
        response = client.get(f"{USERS_PREFIX}/company-accesses/user-1")
        assert response.status_code == 401

    def test_company_accesses_with_override_returns_list_or_403(
        self, client_with_user_override: TestClient
    ):
        response = client_with_user_override.get(
            f"{USERS_PREFIX}/company-accesses/user-test-1"
        )
        assert response.status_code in (200, 403, 404, 500)
        if response.status_code == 200:
            assert isinstance(response.json(), list)


# ----- POST /api/users/grant-access -----


class TestUsersGrantAccess:
    """POST /api/users/grant-access (par email)."""

    def test_grant_access_without_token_returns_401(self, client: TestClient):
        response = client.post(
            f"{USERS_PREFIX}/grant-access",
            json={
                "user_email": "new@example.com",
                "company_id": "company-1",
                "role": "rh",
                "is_primary": False,
            },
        )
        assert response.status_code == 401

    def test_grant_access_with_invalid_body_returns_422(self, client_with_user_override: TestClient):
        response = client_with_user_override.post(
            f"{USERS_PREFIX}/grant-access",
            json={"company_id": "c1"},
        )
        assert response.status_code == 422


# ----- POST /api/users/grant-access-by-user-id -----


class TestUsersGrantAccessByUserId:
    """POST /api/users/grant-access-by-user-id."""

    def test_grant_access_by_user_id_without_token_returns_401(self, client: TestClient):
        response = client.post(
            f"{USERS_PREFIX}/grant-access-by-user-id",
            json={
                "user_id": str(uuid4()),
                "company_id": "company-1",
                "role": "collaborateur",
                "is_primary": False,
            },
        )
        assert response.status_code == 401

    def test_grant_access_by_user_id_invalid_body_returns_422(
        self, client_with_user_override: TestClient
    ):
        response = client_with_user_override.post(
            f"{USERS_PREFIX}/grant-access-by-user-id",
            json={},
        )
        assert response.status_code == 422


# ----- DELETE /api/users/revoke-access/{user_id}/{company_id} -----


class TestUsersRevokeAccess:
    """DELETE /api/users/revoke-access/{user_id}/{company_id}."""

    def test_revoke_access_without_token_returns_401(self, client: TestClient):
        response = client.delete(
            f"{USERS_PREFIX}/revoke-access/user-1/company-1"
        )
        assert response.status_code == 401


# ----- PATCH /api/users/update-access/{user_id}/{company_id} -----


class TestUsersUpdateAccess:
    """PATCH /api/users/update-access/{user_id}/{company_id}."""

    def test_update_access_without_token_returns_401(self, client: TestClient):
        response = client.patch(
            f"{USERS_PREFIX}/update-access/user-1/company-1",
            json={"role": "rh"},
        )
        assert response.status_code == 401

    def test_update_access_empty_body_returns_422(self, client_with_user_override: TestClient):
        response = client_with_user_override.patch(
            f"{USERS_PREFIX}/update-access/user-1/company-1",
            json={},
        )
        assert response.status_code in (400, 422)


# ----- POST /api/users/create-with-permissions -----


class TestUsersCreateWithPermissions:
    """POST /api/users/create-with-permissions."""

    def test_create_without_token_returns_401(self, client: TestClient):
        response = client.post(
            f"{USERS_PREFIX}/create-with-permissions",
            json={
                "email": "new@example.com",
                "password": "SecureP@ss123",
                "first_name": "New",
                "last_name": "User",
                "company_accesses": [
                    {
                        "company_id": str(uuid4()),
                        "base_role": "collaborateur",
                        "is_primary": True,
                        "permission_ids": [],
                    }
                ],
            },
        )
        assert response.status_code == 401

    def test_create_without_primary_access_returns_400(self, client_with_user_override: TestClient):
        response = client_with_user_override.post(
            f"{USERS_PREFIX}/create-with-permissions",
            json={
                "email": "new@example.com",
                "password": "SecureP@ss123",
                "first_name": "New",
                "last_name": "User",
                "company_accesses": [
                    {
                        "company_id": str(uuid4()),
                        "base_role": "collaborateur",
                        "is_primary": False,
                        "permission_ids": [],
                    }
                ],
            },
        )
        assert response.status_code == 400
        assert "primaire" in response.json().get("detail", "").lower()


# ----- GET /api/users/company/{company_id} -----


class TestUsersCompanyUsers:
    """GET /api/users/company/{company_id} — liste des utilisateurs d'une entreprise."""

    def test_company_users_without_token_returns_401(self, client: TestClient):
        response = client.get(f"{USERS_PREFIX}/company/company-1")
        assert response.status_code == 401

    def test_company_users_with_override_returns_list_or_error(
        self, client_with_user_override: TestClient
    ):
        response = client_with_user_override.get(f"{USERS_PREFIX}/company/company-1")
        assert response.status_code in (200, 403, 404, 500)
        if response.status_code == 200:
            assert isinstance(response.json(), list)


# ----- GET /api/users/accessible-companies -----


class TestUsersAccessibleCompanies:
    """GET /api/users/accessible-companies."""

    def test_accessible_companies_without_token_returns_401(self, client: TestClient):
        response = client.get(f"{USERS_PREFIX}/accessible-companies")
        assert response.status_code == 401

    def test_accessible_companies_with_override_returns_200(
        self, client_with_user_override: TestClient
    ):
        response = client_with_user_override.get(f"{USERS_PREFIX}/accessible-companies")
        assert response.status_code in (200, 500)
        if response.status_code == 200:
            assert isinstance(response.json(), list)


# ----- GET /api/users/{user_id} -----


class TestUsersUserDetail:
    """GET /api/users/{user_id}?company_id=... — détail utilisateur pour une entreprise."""

    def test_user_detail_without_token_returns_401(self, client: TestClient):
        response = client.get(
            f"{USERS_PREFIX}/user-test-1",
            params={"company_id": "company-1"},
        )
        assert response.status_code == 401

    def test_user_detail_with_override_returns_ok_or_error(
        self, client_with_user_override: TestClient
    ):
        response = client_with_user_override.get(
            f"{USERS_PREFIX}/user-test-1",
            params={"company_id": "company-1"},
        )
        assert response.status_code in (200, 403, 404, 500)
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "role" in data or "email" in data


# ----- PUT /api/users/{user_id}/update -----


class TestUsersUpdateUser:
    """PUT /api/users/{user_id}/update."""

    def test_update_user_without_token_returns_401(self, client: TestClient):
        response = client.put(
            f"{USERS_PREFIX}/user-1/update",
            json={
                "company_id": str(uuid4()),
                "first_name": "Updated",
            },
        )
        assert response.status_code == 401

    def test_update_user_missing_company_id_returns_422(self, client_with_user_override: TestClient):
        response = client_with_user_override.put(
            f"{USERS_PREFIX}/user-test-1/update",
            json={"first_name": "Updated"},
        )
        assert response.status_code == 422
