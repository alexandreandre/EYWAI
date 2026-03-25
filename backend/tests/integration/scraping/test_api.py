"""
Tests d'intégration HTTP des routes du module scraping.

Routes : GET /dashboard, GET/POST /sources, GET /sources/{id}, POST /execute,
GET /jobs, GET /jobs/{id}, GET /jobs/{id}/logs, GET/POST/PATCH/DELETE /schedules,
GET /alerts, PATCH /alerts/{id}/read, PATCH /alerts/{id}/resolve.
Utilise : client (TestClient), dependency_overrides pour get_current_user et
verify_super_admin ; patch des commands/queries pour éviter DB et scraping réel.

Fixture à ajouter dans tests/conftest.py si besoin de tests E2E avec token réel :
  @pytest.fixture
  def scraping_headers(auth_headers):
      \"\"\"En-têtes pour les routes /api/scraping/* (super admin uniquement).
      Format : {\"Authorization\": \"Bearer <jwt>\"}. L'utilisateur doit être
      présent dans super_admins avec is_active=True.\"\"\"
      return auth_headers
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User

pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_super_admin_user():
    """Utilisateur de test (super admin pour verify_super_admin)."""
    return User(
        id=TEST_USER_ID,
        email="super@scraping-test.com",
        first_name="Super",
        last_name="Admin",
        is_super_admin=True,
        is_group_admin=False,
        accessible_companies=[],
        active_company_id=None,
    )


def _super_admin_dep():
    """Dépendance mock pour verify_super_admin : retourne un dict valide."""
    return {"user_id": TEST_USER_ID, "is_active": True}


# --- Sans auth : 401 ---


class TestScrapingUnauthenticated:
    """Sans token : 401. Avec token mais pas super_admin : 403."""

    def test_get_dashboard_returns_401_without_token(self, client: TestClient):
        """Sans token, GET /api/scraping/dashboard renvoie 401."""
        response = client.get("/api/scraping/dashboard")
        assert response.status_code == 401

    def test_get_dashboard_returns_403_when_not_super_admin(self, client: TestClient):
        """Si verify_super_admin échoue (utilisateur pas super admin), 403."""
        from fastapi import HTTPException
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()

        def fail_super_admin():
            raise HTTPException(
                status_code=403,
                detail="Accès refusé : vous devez être super administrateur",
            )

        app.dependency_overrides[verify_super_admin] = fail_super_admin
        try:
            response = client.get("/api/scraping/dashboard")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 403


# --- Avec super_admin mocké + commands/queries mockés ---


class TestScrapingDashboard:
    """GET /api/scraping/dashboard."""

    def test_get_dashboard_returns_200_with_stats(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.get_scraping_dashboard",
                return_value={
                    "stats": {"total_jobs": 10},
                    "recent_jobs": [],
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
        assert "stats" in data
        assert data["stats"]["total_jobs"] == 10
        assert "recent_jobs" in data
        assert "unread_alerts" in data
        assert "critical_sources" in data


class TestScrapingSources:
    """GET /api/scraping/sources, GET /api/scraping/sources/{source_id}."""

    def test_list_sources_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.list_sources",
                return_value={
                    "sources": [{"id": "src-1", "source_key": "SMIC"}],
                    "total": 1,
                },
            ):
                response = client.get("/api/scraping/sources")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["sources"][0]["source_key"] == "SMIC"

    def test_get_source_details_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.get_source_details",
                return_value={
                    "id": "src-1",
                    "source_name": "SMIC",
                    "jobs_history": [],
                    "schedules": [],
                    "recent_alerts": [],
                },
            ):
                response = client.get("/api/scraping/sources/src-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["id"] == "src-1"
        assert response.json()["source_name"] == "SMIC"

    def test_get_source_details_returns_404_when_not_found(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.get_source_details",
                side_effect=ValueError("Source non trouvée"),
            ):
                response = client.get("/api/scraping/sources/src-unknown")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 404
        assert "Source non trouvée" in response.json().get("detail", "")


class TestScrapingExecute:
    """POST /api/scraping/execute."""

    def test_execute_returns_200_with_job_id(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.execute_scraper",
                return_value={
                    "message": "Scraping lancé en arrière-plan",
                    "source": "SMIC",
                    "source_key": "SMIC",
                    "job_id": "job-123",
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
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["source_key"] == "SMIC"

    def test_execute_returns_404_when_source_not_found(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.execute_scraper",
                side_effect=ValueError("Source non trouvée"),
            ):
                response = client.post(
                    "/api/scraping/execute",
                    json={"source_key": "UNKNOWN", "use_orchestrator": True},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 404


class TestScrapingJobs:
    """GET /api/scraping/jobs, GET /api/scraping/jobs/{job_id}, GET /api/scraping/jobs/{job_id}/logs."""

    def test_list_jobs_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.list_jobs",
                return_value={
                    "jobs": [{"id": "job-1", "status": "completed"}],
                    "total": 1,
                },
            ):
                response = client.get("/api/scraping/jobs")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_get_job_details_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.get_job_details",
                return_value={"id": "job-1", "status": "completed", "success": True},
            ):
                response = client.get("/api/scraping/jobs/job-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["id"] == "job-1"

    def test_get_job_logs_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.get_job_logs",
                return_value={
                    "job_id": "job-1",
                    "status": "completed",
                    "logs": ["log1"],
                    "success": True,
                    "error_message": None,
                    "completed_at": "2025-01-15T12:00:00",
                },
            ):
                response = client.get("/api/scraping/jobs/job-1/logs")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["job_id"] == "job-1"
        assert response.json()["logs"] == ["log1"]


class TestScrapingSchedules:
    """GET/POST/PATCH/DELETE /api/scraping/schedules."""

    def test_list_schedules_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.list_schedules",
                return_value={"schedules": [{"id": "sched-1"}], "total": 1},
            ):
                response = client.get("/api/scraping/schedules")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_create_schedule_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.create_schedule",
                return_value={
                    "success": True,
                    "schedule": {"id": "sched-new", "source_id": "src-1"},
                },
            ):
                response = client.post(
                    "/api/scraping/schedules",
                    json={
                        "source_id": "src-1",
                        "schedule_type": "cron",
                        "cron_expression": "0 0 * * *",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["schedule"]["id"] == "sched-new"

    def test_create_schedule_returns_400_when_cron_missing(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.create_schedule",
                side_effect=ValueError("Expression cron requise"),
            ):
                response = client.post(
                    "/api/scraping/schedules",
                    json={"source_id": "src-1", "schedule_type": "cron"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 400

    def test_update_schedule_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.update_schedule",
                return_value={
                    "success": True,
                    "schedule": {"id": "sched-1", "is_enabled": False},
                },
            ):
                response = client.patch(
                    "/api/scraping/schedules/sched-1",
                    json={"is_enabled": False},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["schedule"]["is_enabled"] is False

    def test_delete_schedule_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.delete_schedule",
                return_value={"success": True, "message": "Planification supprimée"},
            ):
                response = client.delete("/api/scraping/schedules/sched-1")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["success"] is True


class TestScrapingAlerts:
    """GET /api/scraping/alerts, PATCH .../read, PATCH .../resolve."""

    def test_list_alerts_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.queries.list_alerts",
                return_value={"alerts": [{"id": "alert-1"}], "total": 1},
            ):
                response = client.get("/api/scraping/alerts")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["total"] == 1

    def test_mark_alert_read_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.mark_alert_as_read",
                return_value={"success": True},
            ):
                response = client.patch("/api/scraping/alerts/alert-1/read")
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_resolve_alert_returns_200(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.scraping.api.dependencies import verify_super_admin

        app.dependency_overrides[get_current_user] = lambda: _make_super_admin_user()
        app.dependency_overrides[verify_super_admin] = _super_admin_dep
        try:
            with patch(
                "app.modules.scraping.api.router.commands.resolve_alert",
                return_value={"success": True},
            ):
                response = client.patch(
                    "/api/scraping/alerts/alert-1/resolve",
                    json={"resolution_note": "Résolu"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)
            app.dependency_overrides.pop(verify_super_admin, None)

        assert response.status_code == 200
        assert response.json()["success"] is True
