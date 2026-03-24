"""
Tests d'intégration HTTP des routes du module rib_alerts.

Préfixe des routes : /api/rib-alerts.
Utilise : client (TestClient). Pour les tests avec utilisateur authentifié,
dependency_overrides pour get_current_user et patch de get_rib_alerts / mark_rib_alert_read /
resolve_rib_alert pour éviter la DB réelle.

Fixture optionnelle (conftest.py) : rib_alerts_headers — en-têtes pour un utilisateur
avec active_company_id et droits RH. À ajouter si besoin de tests E2E avec token réel :
  @pytest.fixture
  def rib_alerts_headers(auth_headers):
      \"\"\"En-têtes pour GET/PATCH /api/rib-alerts. Utilisateur avec active_company_id.
      Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\" (optionnel).\"\"\"
      return auth_headers  # ou return {**auth_headers, \"X-Active-Company\": \"<company_uuid>\"}
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-rib-alerts-test"
TEST_USER_ID = "user-rib-alerts-test"


def _make_rh_user_with_company():
    """Utilisateur de test avec active_company_id renseigné (requis pour les routes rib_alerts)."""
    return User(
        id=TEST_USER_ID,
        email="rh@rib-alerts.test",
        first_name="RH",
        last_name="RibAlerts",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_user_without_company():
    """Utilisateur sans entreprise active → 403 sur les routes qui exigent company_id."""
    return User(
        id="user-no-company",
        email="noco@test.com",
        first_name="No",
        last_name="Company",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


class TestListRibAlerts:
    """GET /api/rib-alerts."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/rib-alerts")
        assert response.status_code == 401

    def test_with_auth_and_company_returns_200_and_list(self, client: TestClient):
        """Avec utilisateur ayant active_company_id et mock get_rib_alerts → 200 et { alerts, total }."""
        from app.core.security import get_current_user

        mock_result = type("R", (), {"alerts": [{"id": "a1", "company_id": TEST_COMPANY_ID, "alert_type": "rib_modified", "severity": "warning", "title": "T", "message": "M", "details": {}, "is_read": False, "is_resolved": False, "resolved_at": None, "resolution_note": None, "created_at": "2024-01-01T00:00:00Z"}], "total": 1})()
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.get_rib_alerts", return_value=mock_result):
            response = client.get("/api/rib-alerts")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total" in data
        assert data["total"] == 1
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["id"] == "a1"
        assert data["alerts"][0]["alert_type"] == "rib_modified"

    def test_with_auth_without_company_returns_403(self, client: TestClient):
        """Utilisateur sans active_company_id → 403 (MissingCompanyContextError). On n’utilise pas de mock pour que get_rib_alerts soit appelé avec company_id=None et lève."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_without_company()
        # Pas de patch : le router appelle get_rib_alerts(company_id=None) qui lève MissingCompanyContextError → 403
        response = client.get("/api/rib-alerts")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403
        assert "entreprise" in response.json().get("detail", "").lower() or "active" in response.json().get("detail", "").lower()

    def test_with_auth_accepts_query_params(self, client: TestClient):
        """Query params is_read, is_resolved, alert_type, employee_id, limit, offset sont acceptés."""
        from app.core.security import get_current_user

        mock_result = type("R", (), {"alerts": [], "total": 0})()
        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.get_rib_alerts", return_value=mock_result) as mock_get:
            response = client.get(
                "/api/rib-alerts",
                params={"is_read": "true", "is_resolved": "false", "alert_type": "rib_duplicate", "employee_id": "emp-1", "limit": 20, "offset": 0},
            )
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["total"] == 0
        mock_get.assert_called_once()
        call_kw = mock_get.call_args[1]
        assert call_kw["company_id"] == TEST_COMPANY_ID
        filters = call_kw["filters"]
        assert filters.is_read is True
        assert filters.is_resolved is False
        assert filters.alert_type == "rib_duplicate"
        assert filters.employee_id == "emp-1"
        assert filters.limit == 20
        assert filters.offset == 0


class TestPatchMarkRibAlertRead:
    """PATCH /api/rib-alerts/{alert_id}/read."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.patch("/api/rib-alerts/alert-1/read")
        assert response.status_code == 401

    def test_with_auth_and_company_success_returns_200(self, client: TestClient):
        """Marque comme lu : mock retourne True → 200 et { success: true }."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.mark_rib_alert_read", return_value=True):
            response = client.patch("/api/rib-alerts/alert-1/read")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json().get("success") is True

    def test_with_auth_alert_not_found_returns_404(self, client: TestClient):
        """Alerte inexistante → 404."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.mark_rib_alert_read", return_value=False):
            response = client.patch("/api/rib-alerts/alert-unknown/read")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404
        assert "non trouvée" in response.json().get("detail", "").lower() or "not found" in response.json().get("detail", "").lower()

    def test_with_auth_without_company_returns_403(self, client: TestClient):
        """Utilisateur sans active_company_id → 403. Pas de mock pour que mark_rib_alert_read reçoive company_id=None et lève."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_without_company()
        response = client.patch("/api/rib-alerts/alert-1/read")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403


class TestPatchResolveRibAlert:
    """PATCH /api/rib-alerts/{alert_id}/resolve."""

    def test_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.patch("/api/rib-alerts/alert-1/resolve", json={"resolution_note": "OK"})
        assert response.status_code == 401

    def test_with_auth_success_returns_200(self, client: TestClient):
        """Résolution avec body resolution_note → 200 et { success: true }."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.resolve_rib_alert", return_value=True):
            response = client.patch(
                "/api/rib-alerts/alert-1/resolve",
                json={"resolution_note": "Vérifié manuellement"},
            )
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json().get("success") is True

    def test_with_auth_alert_not_found_returns_404(self, client: TestClient):
        """Alerte inexistante → 404."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.resolve_rib_alert", return_value=False):
            response = client.patch("/api/rib-alerts/alert-unknown/resolve", json={})
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404

    def test_with_auth_without_company_returns_403(self, client: TestClient):
        """Utilisateur sans active_company_id → 403. Pas de mock pour que resolve_rib_alert reçoive company_id=None et lève."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user_without_company()
        response = client.patch("/api/rib-alerts/alert-1/resolve", json={})
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_body_resolution_note_optional(self, client: TestClient):
        """Body peut être vide (resolution_note optionnel)."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user_with_company()
        with patch("app.modules.rib_alerts.api.router.resolve_rib_alert", return_value=True):
            response = client.patch("/api/rib-alerts/alert-1/resolve", json={})
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
