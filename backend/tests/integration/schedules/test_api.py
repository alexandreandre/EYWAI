"""
Tests d'intégration HTTP des routes du module schedules.

Routes testées :
- GET/POST /api/employees/{employee_id}/calendar-data (via get_employee_calendar)
- GET/POST /api/employees/{employee_id}/planned-calendar
- GET/POST /api/employees/{employee_id}/actual-hours
- POST /api/employees/{employee_id}/calculate-payroll-events
- GET /api/me/current-cumuls (authentifié)
- POST /api/schedules/apply-model (authentifié RH)

Utilise : client (TestClient), dependency_overrides pour get_current_user,
patch des commands/queries pour éviter DB réelle. Pour tests E2E avec token réel,
ajouter la fixture schedules_headers dans conftest.py (voir doc en fin de conftest).
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.schedules.schemas.responses import CumulsResponse
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_EMPLOYEE_ID = "00000000-0000-0000-0000-000000000001"
TEST_COMPANY_ID = "company-schedules-test"
TEST_RH_USER_ID = "user-rh-schedules-test"


def _make_rh_user():
    """Utilisateur RH avec active_company_id et has_rh_access_in_company(company_id)=True."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_RH_USER_ID,
        email="rh@test.com",
        first_name="RH",
        last_name="Schedules",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_employee_user():
    """Utilisateur collaborateur (pour /api/me/current-cumuls)."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur",
        is_primary=True,
    )
    return User(
        id=TEST_EMPLOYEE_ID,
        email="emp@test.com",
        first_name="Jean",
        last_name="Dupont",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


# --- Routes sans auth (employee_id dans path) : peuvent être 401 si le routeur exige auth ---
# Le routeur schedules n'injecte get_current_user que sur router_me et router_rh,
# donc GET/POST sous /api/employees/{employee_id} peuvent ne pas exiger d'auth selon le projet.
# On teste le comportement réel : 200 avec mocks ou 401 si une dépendance auth est ajoutée.


class TestGetEmployeeCalendarData:
    """GET /api/employees/{employee_id}/calendar-data."""

    def test_get_calendar_data_returns_200_with_mock(self, client: TestClient):
        """Avec query mockée → 200 et structure planned/actual."""
        with patch(
            "app.modules.schedules.api.router.queries.get_employee_calendar",
            return_value={"planned": [], "actual": []},
        ):
            response = client.get(
                f"/api/employees/{TEST_EMPLOYEE_ID}/calendar-data",
                params={"year": 2025, "month": 3},
            )
        assert response.status_code == 200
        data = response.json()
        assert "planned" in data
        assert "actual" in data
        assert isinstance(data["planned"], list)
        assert isinstance(data["actual"], list)


class TestGetPlannedCalendar:
    """GET /api/employees/{employee_id}/planned-calendar."""

    def test_get_planned_calendar_returns_200_with_mock(self, client: TestClient):
        """Avec query mockée → 200, year, month, calendrier_prevu."""
        with patch(
            "app.modules.schedules.api.router.queries.get_planned_calendar",
            return_value={
                "year": 2025,
                "month": 3,
                "calendrier_prevu": [{"jour": 1, "type": "work", "heures_prevues": 8}],
            },
        ):
            response = client.get(
                f"/api/employees/{TEST_EMPLOYEE_ID}/planned-calendar",
                params={"year": 2025, "month": 3},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2025
        assert data["month"] == 3
        assert "calendrier_prevu" in data


class TestPostPlannedCalendar:
    """POST /api/employees/{employee_id}/planned-calendar."""

    def test_post_planned_calendar_invalid_body_returns_422(self, client: TestClient):
        """Body invalide (manque champs) → 422."""
        response = client.post(
            f"/api/employees/{TEST_EMPLOYEE_ID}/planned-calendar",
            json={},
        )
        assert response.status_code == 422

    def test_post_planned_calendar_valid_returns_200_with_mock(self, client: TestClient):
        """Body valide → 200 et status success (commande mockée)."""
        with patch(
            "app.modules.schedules.api.router.commands.update_planned_calendar",
            return_value={"status": "success", "message": "Planning prévisionnel enregistré."},
        ):
            response = client.post(
                f"/api/employees/{TEST_EMPLOYEE_ID}/planned-calendar",
                json={
                    "year": 2025,
                    "month": 3,
                    "calendrier_prevu": [
                        {"jour": 1, "type": "work", "heures_prevues": 8},
                    ],
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"


class TestGetActualHours:
    """GET /api/employees/{employee_id}/actual-hours."""

    def test_get_actual_hours_returns_200_with_mock(self, client: TestClient):
        """Avec query mockée → 200, year, month, calendrier_reel."""
        with patch(
            "app.modules.schedules.api.router.queries.get_actual_hours",
            return_value={
                "year": 2025,
                "month": 3,
                "calendrier_reel": [{"jour": 1, "heures_faites": 7.5}],
            },
        ):
            response = client.get(
                f"/api/employees/{TEST_EMPLOYEE_ID}/actual-hours",
                params={"year": 2025, "month": 3},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2025
        assert data["month"] == 3
        assert "calendrier_reel" in data


class TestPostActualHours:
    """POST /api/employees/{employee_id}/actual-hours."""

    def test_post_actual_hours_invalid_body_returns_422(self, client: TestClient):
        """Body invalide → 422."""
        response = client.post(
            f"/api/employees/{TEST_EMPLOYEE_ID}/actual-hours",
            json={"year": 2025},
        )
        assert response.status_code == 422

    def test_post_actual_hours_valid_returns_200_with_mock(self, client: TestClient):
        """Body valide → 200 (commande mockée)."""
        with patch(
            "app.modules.schedules.api.router.commands.update_actual_hours",
            return_value={"status": "success", "message": "Heures réelles enregistrées."},
        ):
            response = client.post(
                f"/api/employees/{TEST_EMPLOYEE_ID}/actual-hours",
                json={
                    "year": 2025,
                    "month": 3,
                    "calendrier_reel": [{"jour": 1, "heures_faites": 7.5}],
                },
            )
        assert response.status_code == 200


class TestPostCalculatePayrollEvents:
    """POST /api/employees/{employee_id}/calculate-payroll-events."""

    def test_calculate_payroll_events_invalid_body_returns_422_or_500(
        self, client: TestClient
    ):
        """Body sans year/month → 422 ou 500 selon validation."""
        response = client.post(
            f"/api/employees/{TEST_EMPLOYEE_ID}/calculate-payroll-events",
            json={},
        )
        assert response.status_code in (422, 500)

    def test_calculate_payroll_events_valid_returns_200_with_mock(
        self, client: TestClient
    ):
        """Body {year, month} → 200 (commande mockée)."""
        with patch(
            "app.modules.schedules.api.router.commands.calculate_payroll_events",
            return_value={
                "status": "success",
                "message": "5 événements de paie calculés.",
            },
        ):
            response = client.post(
                f"/api/employees/{TEST_EMPLOYEE_ID}/calculate-payroll-events",
                json={"year": 2025, "month": 3},
            )
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"


# --- GET /api/me/current-cumuls (authentifié) ---


class TestGetMyCurrentCumuls:
    """GET /api/me/current-cumuls."""

    def test_get_current_cumuls_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.get("/api/me/current-cumuls")
        assert response.status_code == 401

    def test_get_current_cumuls_with_auth_returns_200_with_mock(self, client: TestClient):
        """Avec get_current_user override et query mockée → 200."""
        from app.core.security import get_current_user

        try:
            app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
            with patch(
                "app.modules.schedules.api.router.queries.get_my_current_cumuls",
                return_value=CumulsResponse(periode=None, cumuls=None),
            ):
                response = client.get("/api/me/current-cumuls")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert "periode" in data
        assert "cumuls" in data


# --- POST /api/schedules/apply-model (RH) ---


class TestPostApplyModel:
    """POST /api/schedules/apply-model."""

    def test_apply_model_without_auth_returns_401(self, client: TestClient):
        """Sans token → 401."""
        response = client.post(
            "/api/schedules/apply-model",
            json={
                "employee_ids": [TEST_EMPLOYEE_ID],
                "year": 2025,
                "month": 3,
                "week_configs": {},
            },
        )
        assert response.status_code == 401

    def test_apply_model_invalid_body_returns_422(self, client: TestClient):
        """Body invalide (week_configs manquant ou mal formé) → 422."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            response = client.post(
                "/api/schedules/apply-model",
                json={
                    "employee_ids": [TEST_EMPLOYEE_ID],
                    "year": 2025,
                    "month": 3,
                },
            )
            assert response.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_apply_model_with_rh_returns_200_with_mock(self, client: TestClient):
        """Utilisateur RH + body valide + commande mockée → 200."""
        from app.core.security import get_current_user

        day_config = {"type": "work", "hours": 8.0}
        week = {
            "monday": day_config,
            "tuesday": day_config,
            "wednesday": day_config,
            "thursday": day_config,
            "friday": day_config,
            "saturday": {"type": "rest", "hours": 0},
            "sunday": {"type": "rest", "hours": 0},
        }
        body = {
            "employee_ids": [TEST_EMPLOYEE_ID],
            "year": 2025,
            "month": 3,
            "week_configs": {
                1: week,
                2: week,
                3: week,
                4: week,
                5: week,
            },
        }

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        with patch(
            "app.modules.schedules.api.router.commands.apply_schedule_model",
            return_value={
                "status": "success",
                "message": "Le modèle a été appliqué à 1 employé(s)",
                "details": {"year": 2025, "month": 3, "employee_count": 1},
            },
        ):
            response = client.post("/api/schedules/apply-model", json=body)
        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("details", {}).get("employee_count") == 1
