"""
Tests de câblage (wiring) du module absences : injection des dépendances et flux bout en bout.

Vérifie que les routes API appellent bien la couche application (commands, queries) et que
le module est correctement monté dans l'app.
"""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-absences-wiring"


class TestAbsencesRouterMounted:
    """Vérification que le router absences est monté et répond."""

    def test_get_absences_root_returns_list(self, client: TestClient):
        """GET /api/absences/ sans auth → 401."""
        response = client.get("/api/absences/")
        assert response.status_code == 401

    def test_get_absences_root_uses_queries_get_absence_requests(
        self, client: TestClient
    ):
        """GET /api/absences/ utilise bien la couche application (queries)."""
        from app.core.security import get_current_user
        from app.main import app
        from app.modules.users.schemas.responses import CompanyAccess, User

        rh_user = User(
            id="user-rh-wiring",
            email="rh@wiring.test",
            first_name="RH",
            last_name="Wiring",
            is_super_admin=False,
            is_group_admin=False,
            accessible_companies=[
                CompanyAccess(
                    company_id=TEST_COMPANY_ID,
                    company_name="Test Co",
                    role="rh",
                    is_primary=True,
                )
            ],
            active_company_id=TEST_COMPANY_ID,
        )
        with patch(
            "app.modules.absences.api.router.queries.get_absence_requests"
        ) as get_requests:
            get_requests.return_value = [
                {
                    "id": "wired-req-1",
                    "created_at": datetime(2025, 6, 1, 9, 0, 0),
                    "employee_id": "emp-1",
                    "employee": {
                        "id": "emp-1",
                        "first_name": "A",
                        "last_name": "B",
                        "balances": [],
                    },
                    "type": "conge_paye",
                    "selected_days": ["2025-06-10"],
                    "comment": None,
                    "status": "pending",
                }
            ]
            app.dependency_overrides[get_current_user] = lambda: rh_user
            try:
                response = client.get("/api/absences/")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == "wired-req-1"
            get_requests.assert_called_once_with(None, company_id=TEST_COMPANY_ID)

    def test_get_absences_with_status_passes_filter(self, client: TestClient):
        """GET /api/absences/?status=pending transmet le paramètre à get_absence_requests."""
        from app.core.security import get_current_user
        from app.main import app
        from app.modules.users.schemas.responses import CompanyAccess, User

        rh_user = User(
            id="user-rh-wiring",
            email="rh@wiring.test",
            first_name="RH",
            last_name="Wiring",
            is_super_admin=False,
            is_group_admin=False,
            accessible_companies=[
                CompanyAccess(
                    company_id=TEST_COMPANY_ID,
                    company_name="Test Co",
                    role="rh",
                    is_primary=True,
                )
            ],
            active_company_id=TEST_COMPANY_ID,
        )
        with patch(
            "app.modules.absences.api.router.queries.get_absence_requests"
        ) as get_requests:
            get_requests.return_value = []
            app.dependency_overrides[get_current_user] = lambda: rh_user
            try:
                response = client.get("/api/absences/?status=pending")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
            assert response.status_code == 200
            get_requests.assert_called_once_with("pending", company_id=TEST_COMPANY_ID)


class TestAbsencesCreateRequestWiring:
    """Vérification du flux POST /api/absences/requests → commands.create_absence_request."""

    def test_post_requests_calls_create_absence_request_command(
        self, client: TestClient
    ):
        """POST /api/absences/requests appelle commands.create_absence_request avec le body validé."""
        created = {
            "id": "created-1",
            "employee_id": "emp-1",
            "company_id": "comp-1",
            "type": "conge_paye",
            "selected_days": ["2025-06-10"],
            "status": "pending",
            "comment": None,
            "manager_id": None,
            "attachment_url": None,
            "filename": None,
            "event_subtype": None,
            "jours_payes": None,
            "created_at": datetime(2025, 6, 1, 9, 0, 0),
        }
        with patch(
            "app.modules.absences.api.router.commands.create_absence_request"
        ) as create_cmd, patch(
            "app.modules.absences.api.router.absence_repository.get_team_manager_employee_id_for_employee",
            return_value=None,
        ), patch(
            "app.modules.absences.api.router.absence_repository.update",
            side_effect=lambda rid, payload: {**created, **payload},
        ):
            create_cmd.return_value = created
            response = client.post(
                "/api/absences/requests",
                json={
                    "employee_id": "emp-1",
                    "type": "conge_paye",
                    "selected_days": ["2025-06-10"],
                },
            )
            assert response.status_code == 201
            data = response.json()
            assert data["id"] == "created-1"
            create_cmd.assert_called_once()
            call_args = create_cmd.call_args[0][0]
            assert call_args.employee_id == "emp-1"
            assert call_args.type == "conge_paye"
            assert len(call_args.selected_days) == 1
            assert call_args.selected_days[0] == date(2025, 6, 10)


class TestAbsencesCommandsQueriesWiring:
    """Vérification que commands et queries utilisent le repository et les providers."""

    def test_create_absence_request_uses_repository(self):
        """create_absence_request (command) utilise absence_repository.create."""
        from app.modules.absences.application import commands

        with patch(
            "app.modules.absences.application.commands.get_employee_company_id",
            return_value="comp-1",
        ):
            with patch(
                "app.modules.absences.application.commands.absence_repository"
            ) as repo:
                repo.create.return_value = {"id": "r1", "status": "pending"}
                request_data = type(
                    "Req",
                    (),
                    {
                        "selected_days": [date(2025, 6, 10)],
                        "type": "conge_paye",
                        "employee_id": "emp-1",
                        "event_subtype": None,
                        "comment": None,
                        "attachment_url": None,
                        "filename": None,
                    },
                )()
                result = commands.create_absence_request(request_data)
                assert result["id"] == "r1"
                repo.create.assert_called_once()

    def test_get_absence_requests_uses_repository(self):
        """get_absence_requests (query) utilise absence_repository.list_by_status."""
        from app.modules.absences.application import queries

        with patch(
            "app.modules.absences.application.queries.absence_repository"
        ) as repo:
            repo.list_by_status.return_value = []
            result = queries.get_absence_requests(
                status="validated", company_id=TEST_COMPANY_ID
            )
            assert result == []
            repo.list_by_status.assert_called_once_with(
                "validated", company_id=TEST_COMPANY_ID
            )
