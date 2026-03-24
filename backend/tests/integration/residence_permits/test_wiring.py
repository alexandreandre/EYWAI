"""
Tests de câblage (wiring) du module residence_permits.

Vérifient que l'injection des dépendances et le flux de bout en bout sont corrects :
router monté sous /api/residence-permits, get_current_user utilisé,
get_residence_permits_list appelé avec company_id dérivé de l'utilisateur RH.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem
from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-residence-permits-wiring"
TEST_USER_ID = "user-residence-permits-wiring"


def _make_rh_user():
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_USER_ID,
        email="rh@residence-test.com",
        first_name="RH",
        last_name="Residence",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


class TestResidencePermitsRouterMounted:
    """Vérification que le router residence_permits est monté sous /api/residence-permits."""

    def test_route_returns_401_without_auth(self, client: TestClient):
        """GET /api/residence-permits exige une authentification (401 sans token)."""
        response = client.get("/api/residence-permits")
        assert response.status_code == 401


class TestResidencePermitsFlowEndToEnd:
    """Flux bout en bout : query appelée depuis la route avec le bon company_id."""

    def test_get_list_calls_query_with_company_id_from_user(self, client: TestClient):
        """
        GET /api/residence-permits avec auth : après get_current_user et
        _require_rh_company_context, get_residence_permits_list est appelée
        avec active_company_id de l'utilisateur.
        """
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
            mock_list.assert_called_once()
            assert mock_list.call_args[0][0] == TEST_COMPANY_ID
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["employee_id"] == "emp-1"
        finally:
            app.dependency_overrides.pop(get_current_user, None)
