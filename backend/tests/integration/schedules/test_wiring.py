"""
Tests de câblage (wiring) du module schedules.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application commands/queries -> repository / providers) fonctionnent.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-schedules-wiring"
TEST_EMPLOYEE_ID = "00000000-0000-0000-0000-000000000111"
TEST_RH_USER_ID = "user-rh-wiring"


def _rh_user():
    """Utilisateur RH avec active_company_id et has_rh_access_in_company."""
    return User(
        id=TEST_RH_USER_ID,
        email="rh@wiring.test",
        first_name="RH",
        last_name="Wiring",
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


def _employee_user():
    """Utilisateur collaborateur (id = employee_id pour /api/me)."""
    return User(
        id=TEST_EMPLOYEE_ID,
        email="emp@wiring.test",
        first_name="Jean",
        last_name="Wiring",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Wiring Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestSchedulesWiringPlannedCalendar:
    """Flux GET/POST planned-calendar : router -> queries/commands -> repository."""

    def test_get_planned_calendar_flow_uses_queries_and_repository(
        self, client: TestClient
    ):
        """GET /api/employees/{id}/planned-calendar appelle queries.get_planned_calendar qui utilise le repo."""
        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_planned_calendar.return_value = {
                "calendrier_prevu": [{"jour": 1, "type": "work", "heures_prevues": 8}],
            }

            response = client.get(
                f"/api/employees/{TEST_EMPLOYEE_ID}/planned-calendar",
                params={"year": 2025, "month": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["year"] == 2025
        assert data["month"] == 3
        assert len(data["calendrier_prevu"]) == 1
        assert data["calendrier_prevu"][0]["jour"] == 1
        repo.get_planned_calendar.assert_called_once_with(
            TEST_EMPLOYEE_ID, 2025, 3
        )

    def test_post_planned_calendar_flow_uses_commands_and_repository(
        self, client: TestClient
    ):
        """POST /api/employees/{id}/planned-calendar appelle commands.update_planned_calendar -> repo.upsert_schedule."""
        with patch(
            "app.modules.schedules.application.commands.get_employee_company_and_statut",
            return_value=(TEST_COMPANY_ID, "employé"),
        ), patch(
            "app.modules.schedules.application.commands.schedule_repository",
        ) as repo:
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
        repo.upsert_schedule.assert_called_once()
        call_args = repo.upsert_schedule.call_args
        assert call_args[0][0] == TEST_EMPLOYEE_ID
        assert call_args[0][1] == TEST_COMPANY_ID
        assert call_args[0][2] == 2025
        assert call_args[0][3] == 3
        assert "planned_calendar" in call_args[1]


class TestSchedulesWiringActualHours:
    """Flux GET/POST actual-hours."""

    def test_get_actual_hours_flow_uses_repository(self, client: TestClient):
        """GET /api/employees/{id}/actual-hours -> queries.get_actual_hours -> repo.get_actual_hours."""
        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_actual_hours.return_value = {
                "calendrier_reel": [{"jour": 1, "heures_faites": 7.5}],
            }

            response = client.get(
                f"/api/employees/{TEST_EMPLOYEE_ID}/actual-hours",
                params={"year": 2025, "month": 3},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["calendrier_reel"][0]["jour"] == 1
        assert data["calendrier_reel"][0]["heures_faites"] == 7.5
        repo.get_actual_hours.assert_called_once_with(TEST_EMPLOYEE_ID, 2025, 3)


class TestSchedulesWiringMeCumuls:
    """Flux GET /api/me/current-cumuls."""

    def test_get_my_current_cumuls_flow_uses_queries_and_repository(
        self, client: TestClient
    ):
        """GET /api/me/current-cumuls : get_current_user -> queries.get_my_current_cumuls -> repo.get_latest_cumuls_row."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.schedules.application.queries.schedule_repository",
        ) as repo:
            repo.get_latest_cumuls_row.return_value = {
                "cumuls": {
                    "periode": {"annee_en_cours": 2025, "dernier_mois_calcule": 3},
                    "cumuls": {"brut_total": 3000.0, "heures_remunerees": 151.67},
                },
            }

            app.dependency_overrides[get_current_user] = lambda: _employee_user()
            try:
                response = client.get("/api/me/current-cumuls")
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data.get("periode") is not None
        assert data.get("cumuls") is not None
        assert data["cumuls"].get("brut_total") == 3000.0
        repo.get_latest_cumuls_row.assert_called_once_with(TEST_EMPLOYEE_ID)


class TestSchedulesWiringApplyModel:
    """Flux POST /api/schedules/apply-model."""

    def test_apply_model_flow_uses_commands_and_repository(
        self, client: TestClient
    ):
        """POST /api/schedules/apply-model : get_current_user -> commands.apply_schedule_model -> employee_company_reader + repo."""
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
            "week_configs": {1: week, 2: week, 3: week, 4: week, 5: week},
        }

        with patch(
            "app.modules.schedules.application.commands.employee_company_reader",
        ) as reader, patch(
            "app.modules.schedules.application.commands.schedule_repository",
        ) as repo:
            reader.get_company_and_statut.return_value = (TEST_COMPANY_ID, "employé")
            repo.exists_schedule.return_value = False
            app.dependency_overrides[get_current_user] = lambda: _rh_user()
            try:
                response = client.post("/api/schedules/apply-model", json=body)
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "success"
        assert data.get("details", {}).get("employee_count") == 1
        reader.get_company_and_statut.assert_called_once_with(TEST_EMPLOYEE_ID)
        repo.insert_schedule.assert_called_once()
        call_args = repo.insert_schedule.call_args[0]
        assert call_args[0] == TEST_EMPLOYEE_ID
        assert call_args[1] == TEST_COMPANY_ID
        assert call_args[2] == 2025
        assert call_args[3] == 3
