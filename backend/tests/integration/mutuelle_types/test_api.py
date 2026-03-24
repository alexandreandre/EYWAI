"""
Tests d'intégration HTTP des routes du module mutuelle_types.

Routes : GET /api/mutuelle-types, POST /api/mutuelle-types,
PUT /api/mutuelle-types/{id}, DELETE /api/mutuelle-types/{id}.
Utilise : client (TestClient), dependency_overrides pour get_current_user,
et patch des fonctions application (list_mutuelle_types, create_mutuelle_type, etc.)
pour éviter la DB réelle.
"""
from datetime import datetime
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_RH_USER_ID):
    """Utilisateur de test avec droits RH sur l'entreprise et active_company_id."""
    return User(
        id=user_id,
        email="rh@mutuelle-test.com",
        first_name="RH",
        last_name="Mutuelle",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_employee_user(company_id: str = TEST_COMPANY_ID):
    """Utilisateur sans droits RH (collaborateur)."""
    return User(
        id="770e8400-e29b-41d4-a716-446655440002",
        email="emp@mutuelle-test.com",
        first_name="Emp",
        last_name="Mutuelle",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_super_admin_user(company_id: str = TEST_COMPANY_ID):
    """Utilisateur super admin (peut supprimer sans être RH)."""
    return User(
        id="880e8400-e29b-41d4-a716-446655440003",
        email="admin@mutuelle-test.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=company_id,
    )


class TestMutuelleTypesUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_list_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/mutuelle-types")
        assert response.status_code == 401

    def test_post_create_returns_401_without_auth(self, client: TestClient):
        response = client.post(
            "/api/mutuelle-types",
            json={
                "libelle": "Formule Standard",
                "montant_salarial": 50.0,
                "montant_patronal": 30.0,
                "part_patronale_soumise_a_csg": True,
                "is_active": True,
                "employee_ids": [],
            },
        )
        assert response.status_code == 401

    def test_put_update_returns_401_without_auth(self, client: TestClient):
        response = client.put(
            f"/api/mutuelle-types/{uuid4()}",
            json={"libelle": "Formule mise à jour"},
        )
        assert response.status_code == 401

    def test_delete_returns_401_without_auth(self, client: TestClient):
        response = client.delete(f"/api/mutuelle-types/{uuid4()}")
        assert response.status_code == 401


class TestMutuelleTypesGetList:
    """GET /api/mutuelle-types."""

    def test_get_list_with_rh_user_returns_200_and_list(self, client: TestClient):
        from app.core.security import get_current_user

        mock_list = [
            {
                "id": str(uuid4()),
                "company_id": TEST_COMPANY_ID,
                "libelle": "Formule A",
                "montant_salarial": 50.0,
                "montant_patronal": 30.0,
                "part_patronale_soumise_a_csg": True,
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": None,
                "created_by": None,
                "employee_ids": ["emp-1"],
            },
        ]
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.api.router.list_mutuelle_types",
                return_value=mock_list,
            ):
                response = client.get("/api/mutuelle-types")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["libelle"] == "Formule A"
        assert data[0]["montant_salarial"] == 50.0
        assert data[0]["employee_ids"] == ["emp-1"]

    def test_get_list_without_active_company_returns_400(self, client: TestClient):
        from app.core.security import get_current_user

        user = _make_rh_user()
        user.active_company_id = None
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.get("/api/mutuelle-types")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 400
        assert "entreprise active" in response.json().get("detail", "").lower()


class TestMutuelleTypesPostCreate:
    """POST /api/mutuelle-types."""

    def test_create_with_rh_user_returns_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = {
            "id": str(uuid4()),
            "company_id": TEST_COMPANY_ID,
            "libelle": "Nouvelle formule",
            "montant_salarial": 60.0,
            "montant_patronal": 40.0,
            "part_patronale_soumise_a_csg": True,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": None,
            "created_by": TEST_RH_USER_ID,
            "employee_ids": [],
        }
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.api.router.create_mutuelle_type",
                return_value=created,
            ):
                response = client.post(
                    "/api/mutuelle-types",
                    json={
                        "libelle": "Nouvelle formule",
                        "montant_salarial": 60.0,
                        "montant_patronal": 40.0,
                        "part_patronale_soumise_a_csg": True,
                        "is_active": True,
                        "employee_ids": [],
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["libelle"] == "Nouvelle formule"
        assert body["montant_salarial"] == 60.0
        assert body["montant_patronal"] == 40.0

    def test_create_with_employee_user_returns_403(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
        try:
            response = client.post(
                "/api/mutuelle-types",
                json={
                    "libelle": "Formule",
                    "montant_salarial": 50.0,
                    "montant_patronal": 30.0,
                    "part_patronale_soumise_a_csg": True,
                    "is_active": True,
                    "employee_ids": [],
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403
        assert "Admin" in response.json().get("detail", "") or "RH" in response.json().get("detail", "")

    def test_create_with_invalid_body_returns_422(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.post(
                "/api/mutuelle-types",
                json={
                    "libelle": "",  # min_length=1
                    "montant_salarial": -1,  # ge=0
                    "montant_patronal": 30.0,
                    "part_patronale_soumise_a_csg": True,
                    "is_active": True,
                    "employee_ids": [],
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422


class TestMutuelleTypesPutUpdate:
    """PUT /api/mutuelle-types/{mutuelle_type_id}."""

    def test_update_with_rh_user_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        mutuelle_id = str(uuid4())
        updated = {
            "id": mutuelle_id,
            "company_id": TEST_COMPANY_ID,
            "libelle": "Formule mise à jour",
            "montant_salarial": 70.0,
            "montant_patronal": 45.0,
            "part_patronale_soumise_a_csg": True,
            "is_active": True,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "created_by": TEST_RH_USER_ID,
            "employee_ids": [],
        }
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.api.router.update_mutuelle_type",
                return_value=updated,
            ):
                response = client.put(
                    f"/api/mutuelle-types/{mutuelle_id}",
                    json={
                        "libelle": "Formule mise à jour",
                        "montant_salarial": 70.0,
                        "montant_patronal": 45.0,
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["libelle"] == "Formule mise à jour"
        assert response.json()["montant_salarial"] == 70.0

    def test_update_without_active_company_returns_400(self, client: TestClient):
        from app.core.security import get_current_user

        user = _make_rh_user()
        user.active_company_id = None
        app.dependency_overrides[get_current_user] = lambda: user
        try:
            response = client.put(
                f"/api/mutuelle-types/{uuid4()}",
                json={"libelle": "X"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 400


class TestMutuelleTypesDelete:
    """DELETE /api/mutuelle-types/{mutuelle_type_id}."""

    def test_delete_with_rh_user_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        mutuelle_id = str(uuid4())
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.mutuelle_types.api.router.delete_mutuelle_type",
                return_value={"status": "success", "message": "Formule de mutuelle supprimée avec succès"},
            ):
                response = client.delete(f"/api/mutuelle-types/{mutuelle_id}")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json().get("status") == "success"
        assert "supprimée" in response.json().get("message", "").lower()

    def test_delete_with_super_admin_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        mutuelle_id = str(uuid4())
        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        try:
            with patch(
                "app.modules.mutuelle_types.api.router.delete_mutuelle_type",
                return_value={"status": "success", "message": "Formule de mutuelle supprimée avec succès"},
            ):
                response = client.delete(f"/api/mutuelle-types/{mutuelle_id}")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200

    def test_delete_with_employee_user_returns_403(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
        try:
            response = client.delete(f"/api/mutuelle-types/{uuid4()}")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 403
