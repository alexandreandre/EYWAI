"""
Tests d'intégration HTTP des routes du module residence_permits.

Route : GET /api/residence-permits (liste des salariés soumis au titre de séjour).
Utilise : client (TestClient), dependency_overrides pour get_current_user,
et mock de get_residence_permits_list pour éviter la DB réelle.

Fixture documentée : residence_permits_headers
  À ajouter dans conftest.py si besoin de tests E2E avec token réel :
  En-têtes pour un utilisateur avec active_company_id et droits RH
  (GET /api/residence-permits). Format : {"Authorization": "Bearer <jwt>",
  "X-Active-Company": "<company_id>" (optionnel). À compléter : retourner
  auth_headers quand auth_headers fournit un JWT valide pour un utilisateur
  ayant active_company_id et has_rh_access_in_company(active_company_id)=True.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_RH_USER_ID):
    """Utilisateur de test avec droits RH et active_company_id."""
    return User(
        id=user_id,
        email="rh@residence-permits-test.com",
        first_name="RH",
        last_name="Residence",
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


def _make_user_no_company():
    """Utilisateur sans entreprise active (400 sur GET liste)."""
    return User(
        id=TEST_RH_USER_ID,
        email="noco@test.com",
        first_name="No",
        last_name="Company",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _make_user_no_rh_access(company_id: str = TEST_COMPANY_ID):
    """Utilisateur avec entreprise active mais sans droit RH (403)."""
    return User(
        id="770e8400-e29b-41d4-a716-446655440002",
        email="collab@test.com",
        first_name="Collab",
        last_name="Test",
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


class TestGetResidencePermitsListUnauthenticated:
    """GET /api/residence-permits sans authentification."""

    def test_returns_401_without_auth(self, client: TestClient):
        """Sans token Bearer → 401."""
        response = client.get("/api/residence-permits")
        assert response.status_code == 401


class TestGetResidencePermitsListAuthenticated:
    """GET /api/residence-permits avec utilisateur injecté et query mockée."""

    def test_returns_400_when_no_active_company(self, client: TestClient):
        """Utilisateur sans active_company_id → 400."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_no_company()
        try:
            response = client.get("/api/residence-permits")
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert (
                "entreprise" in data["detail"].lower()
                or "active" in data["detail"].lower()
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_returns_403_when_no_rh_access(self, client: TestClient):
        """Utilisateur avec active_company_id mais sans droit RH → 403."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_no_rh_access()
        try:
            response = client.get("/api/residence-permits")
            assert response.status_code == 403
            data = response.json()
            assert "detail" in data
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_returns_200_and_list_with_rh_user(self, client: TestClient):
        """Utilisateur RH + active_company_id : GET retourne 200 et liste (mockée)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.residence_permits.api.router.get_residence_permits_list"
            ) as mock_list:
                mock_list.return_value = [
                    ResidencePermitListItem(
                        employee_id="emp-1",
                        first_name="Jean",
                        last_name="Dupont",
                        is_subject_to_residence_permit=True,
                        residence_permit_status="valid",
                        residence_permit_expiry_date="2026-06-15",
                        residence_permit_days_remaining=90,
                        residence_permit_data_complete=True,
                        residence_permit_type=None,
                        residence_permit_number=None,
                    ),
                ]
                response = client.get("/api/residence-permits")
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["employee_id"] == "emp-1"
            assert data[0]["first_name"] == "Jean"
            assert data[0]["residence_permit_status"] == "valid"
            assert data[0]["residence_permit_days_remaining"] == 90
            mock_list.assert_called_once_with(TEST_COMPANY_ID)
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_returns_empty_list_when_no_employees(self, client: TestClient):
        """Query retourne liste vide → 200 et []."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.residence_permits.api.router.get_residence_permits_list"
            ) as mock_list:
                mock_list.return_value = []
                response = client.get("/api/residence-permits")
            assert response.status_code == 200
            assert response.json() == []
            mock_list.assert_called_once_with(TEST_COMPANY_ID)
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_exception_from_query_returns_500(self, client: TestClient):
        """Si get_residence_permits_list lève une exception → 500."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            with patch(
                "app.modules.residence_permits.api.router.get_residence_permits_list"
            ) as mock_list:
                mock_list.side_effect = RuntimeError("DB error")
                response = client.get("/api/residence-permits")
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert (
                "erreur" in data["detail"].lower() or "error" in data["detail"].lower()
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
