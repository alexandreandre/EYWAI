"""
Tests de câblage (wiring) du module rib_alerts.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application commands/queries -> repository) fonctionnent pour ce module.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-rib-wiring"
TEST_USER_ID = "user-rib-wiring"


def _rh_user():
    """Utilisateur avec active_company_id pour les routes rib_alerts."""
    return User(
        id=TEST_USER_ID,
        email="rh@rib.test",
        first_name="RH",
        last_name="Rib",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Wiring Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestRibAlertsWiringList:
    """Flux GET /api/rib-alerts : router -> get_rib_alerts (query) -> repository."""

    def test_list_flow_uses_get_rib_alerts(self, client: TestClient):
        """GET /api/rib-alerts appelle get_rib_alerts qui utilise le repository."""
        from app.core.security import get_current_user

        # Mock au niveau application : get_rib_alerts retourne un résultat
        mock_result = type(
            "R",
            (),
            {
                "alerts": [
                    {
                        "id": "a1",
                        "company_id": TEST_COMPANY_ID,
                        "alert_type": "rib_modified",
                        "severity": "warning",
                        "title": "T",
                        "message": "M",
                        "details": {},
                        "is_read": False,
                        "is_resolved": False,
                        "resolved_at": None,
                        "resolution_note": None,
                        "created_at": "2024-01-01T00:00:00Z",
                    }
                ],
                "total": 1,
            },
        )()
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.rib_alerts.api.router.get_rib_alerts", return_value=mock_result
        ):
            response = client.get("/api/rib-alerts")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["id"] == "a1"

    def test_list_flow_repository_invoked_via_application(self, client: TestClient):
        """En patchant get_rib_alert_repository dans queries, le flux router -> get_rib_alerts -> repo fonctionne."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        from app.modules.rib_alerts.domain.entities import RibAlert

        alert_entity = RibAlert(
            id="a1",
            company_id=TEST_COMPANY_ID,
            employee_id=None,
            alert_type="rib_modified",
            severity="warning",
            title="T",
            message="M",
            details={},
            is_read=False,
            is_resolved=False,
            created_at=datetime.now(timezone.utc),
        )
        mock_repo.list.return_value = ([alert_entity], 1)
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.rib_alerts.application.queries.get_rib_alert_repository",
            return_value=mock_repo,
        ):
            response = client.get("/api/rib-alerts?limit=10&offset=0")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        mock_repo.list.assert_called_once()
        call_kw = mock_repo.list.call_args[1]
        assert call_kw["limit"] == 10
        assert call_kw["offset"] == 0
        assert call_kw.get("alert_type") is None


class TestRibAlertsWiringMarkRead:
    """Flux PATCH /api/rib-alerts/{id}/read : router -> mark_rib_alert_read -> repository."""

    def test_mark_read_flow_uses_command(self, client: TestClient):
        """PATCH .../read appelle mark_rib_alert_read qui utilise le repository."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.mark_read.return_value = True
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.rib_alerts.application.commands.get_rib_alert_repository",
            return_value=mock_repo,
        ):
            response = client.patch("/api/rib-alerts/alert-1/read")
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json().get("success") is True
        mock_repo.mark_read.assert_called_once_with("alert-1", TEST_COMPANY_ID)


class TestRibAlertsWiringResolve:
    """Flux PATCH /api/rib-alerts/{id}/resolve : router -> resolve_rib_alert -> repository."""

    def test_resolve_flow_uses_command(self, client: TestClient):
        """PATCH .../resolve appelle resolve_rib_alert qui utilise le repository."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.resolve.return_value = True
        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch(
            "app.modules.rib_alerts.application.commands.get_rib_alert_repository",
            return_value=mock_repo,
        ):
            response = client.patch(
                "/api/rib-alerts/alert-1/resolve",
                json={"resolution_note": "Résolu"},
            )
        app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json().get("success") is True
        mock_repo.resolve.assert_called_once_with(
            "alert-1", TEST_COMPANY_ID, TEST_USER_ID, "Résolu"
        )
