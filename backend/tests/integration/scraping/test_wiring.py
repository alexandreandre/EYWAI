"""
Tests de câblage (wiring) du module scraping.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application commands/queries -> repository) fonctionnent pour ce module.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User

pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_super_admin_user():
    return User(
        id=TEST_USER_ID,
        email="super@scraping-wiring.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _super_admin_dep():
    return {"user_id": TEST_USER_ID, "is_active": True}


class TestScrapingWiringDashboard:
    """Flux GET /api/scraping/dashboard : router -> queries.get_scraping_dashboard -> infra."""

    def test_dashboard_flow_uses_queries_and_returns_structure(
        self, client: TestClient
    ):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.application.queries.infra_get_dashboard_data",
                return_value={
                    "stats": {"total_jobs": 5},
                    "recent_jobs": [{"id": "j1"}],
                    "unread_alerts": [],
                    "critical_sources": [],
                },
            ):
                response = client.get("/api/scraping/dashboard")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        data = response.json()
        assert data["stats"]["total_jobs"] == 5
        assert len(data["recent_jobs"]) == 1
        assert data["recent_jobs"][0]["id"] == "j1"


class TestScrapingWiringExecute:
    """Flux POST /api/scraping/execute : router -> commands.execute_scraper (repo + scraper_runner)."""

    def test_execute_flow_calls_command_and_returns_job_id(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.application.commands.execute_scraper",
                return_value={
                    "message": "Scraping lancé en arrière-plan",
                    "source": "SMIC",
                    "source_key": "SMIC",
                    "job_id": "job-wiring-1",
                },
            ):
                response = client.post(
                    "/api/scraping/execute",
                    json={"source_key": "SMIC", "use_orchestrator": True},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["job_id"] == "job-wiring-1"
        assert response.json()["source_key"] == "SMIC"


class TestScrapingWiringSchedules:
    """Flux GET/POST/PATCH/DELETE /api/scraping/schedules : router -> commands/queries."""

    def test_list_schedules_flow_returns_schedules(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.application.queries.ScrapingRepository",
                return_value=MagicMock(
                    **{"list_schedules.return_value": [{"id": "s1"}]}
                ),
            ):
                # list_schedules est appelée depuis queries.list_schedules qui utilise _repo()
                with patch(
                    "app.modules.scraping.application.queries.infra_get_dashboard_data",
                    return_value={
                        "stats": {},
                        "recent_jobs": [],
                        "unread_alerts": [],
                        "critical_sources": [],
                    },
                ):
                    pass  # pour dashboard on a déjà un test
                with patch(
                    "app.modules.scraping.api.router.queries.list_schedules",
                    return_value={
                        "schedules": [{"id": "s1", "source_id": "src-1"}],
                        "total": 1,
                    },
                ):
                    response = client.get("/api/scraping/schedules")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["schedules"][0]["id"] == "s1"

    def test_create_schedule_flow_calls_command(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.create_schedule",
                return_value={"success": True, "schedule": {"id": "s-new"}},
            ) as mock_create:
                response = client.post(
                    "/api/scraping/schedules",
                    json={
                        "source_id": "src-1",
                        "schedule_type": "cron",
                        "cron_expression": "0 0 * * *",
                    },
                )
                assert mock_create.called
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestScrapingWiringAlerts:
    """Flux GET /api/scraping/alerts et PATCH read/resolve."""

    def test_list_alerts_flow_returns_alerts(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.list_alerts",
                return_value={
                    "alerts": [{"id": "a1", "severity": "warning"}],
                    "total": 1,
                },
            ):
                response = client.get("/api/scraping/alerts")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["alerts"][0]["id"] == "a1"

    def test_resolve_alert_flow_calls_command_with_user_id(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.resolve_alert",
                return_value={"success": True},
            ) as mock_resolve:
                response = client.patch(
                    "/api/scraping/alerts/alert-1/resolve",
                    json={"resolution_note": "Résolu"},
                )
                mock_resolve.assert_called_once()
                # resolved_by doit être l'id du current_user
                call_kw = mock_resolve.call_args[1]
                assert call_kw.get("resolved_by") == TEST_USER_ID
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
