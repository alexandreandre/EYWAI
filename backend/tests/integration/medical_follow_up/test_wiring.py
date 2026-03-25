"""
Tests de câblage (wiring) du module medical_follow_up.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application -> repository / provider) fonctionnent.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-medical-wiring-test"
TEST_USER_ID = "user-wiring-rh"


def _rh_user():
    """Utilisateur RH avec active_company_id."""
    return User(
        id=TEST_USER_ID,
        email="rh@test.com",
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


class TestMedicalFollowUpWiring:
    """Flux complet : route -> commandes/queries -> repository."""

    def test_list_obligations_flow_uses_repository(self, client: TestClient):
        """GET /api/medical-follow-up/obligations : le router appelle queries.list_obligations qui utilise le repo."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.list_for_company.return_value = [
            {
                "id": "obl-1",
                "company_id": TEST_COMPANY_ID,
                "employee_id": "emp-1",
                "visit_type": "vip",
                "trigger_type": "periodicite_vip",
                "due_date": "2025-06-01",
                "priority": 1,
                "status": "a_faire",
                "rule_source": "legal",
            },
        ]

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with (
            patch(
                "app.modules.medical_follow_up.application.queries.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.commands.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
        ):
            response = client.get("/api/medical-follow-up/obligations")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "obl-1"
        assert data[0]["visit_type"] == "vip"
        mock_repo.list_for_company.assert_called_once()
        assert mock_repo.list_for_company.call_args[0][0] == TEST_COMPANY_ID

    def test_get_kpis_flow_uses_repository(self, client: TestClient):
        """GET /api/medical-follow-up/kpis : queries.get_kpis -> repo.get_kpis."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_kpis.return_value = {
            "overdue_count": 1,
            "due_within_30_count": 2,
            "active_total": 3,
            "completed_this_month": 1,
        }

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with (
            patch(
                "app.modules.medical_follow_up.application.queries.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.commands.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
        ):
            response = client.get("/api/medical-follow-up/kpis")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        body = response.json()
        assert body["overdue_count"] == 1
        assert body["due_within_30_count"] == 2
        assert body["active_total"] == 3
        mock_repo.get_kpis.assert_called_once_with(TEST_COMPANY_ID)

    def test_mark_planified_flow_uses_repository(self, client: TestClient):
        """PATCH .../obligations/{id}/planified : commands.mark_planified -> repo.obligation_exists + repo.mark_planified."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.obligation_exists.return_value = True

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with (
            patch(
                "app.modules.medical_follow_up.application.queries.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.commands.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
        ):
            response = client.patch(
                "/api/medical-follow-up/obligations/obl-1/planified",
                json={"planned_date": "2025-04-15", "justification": "RDV"},
            )

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_repo.obligation_exists.assert_called_once_with("obl-1", TEST_COMPANY_ID)
        mock_repo.mark_planified.assert_called_once_with(
            "obl-1", TEST_COMPANY_ID, "2025-04-15", "RDV"
        )

    def test_create_on_demand_flow_uses_repository(self, client: TestClient):
        """POST .../obligations/on-demand : commands.create_on_demand -> repo.employee_exists + repo.create_on_demand."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.employee_exists.return_value = True

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with (
            patch(
                "app.modules.medical_follow_up.application.queries.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.commands.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
        ):
            response = client.post(
                "/api/medical-follow-up/obligations/on-demand",
                json={
                    "employee_id": "emp-1",
                    "request_motif": "Demande",
                    "request_date": "2025-03-17",
                },
            )

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_repo.employee_exists.assert_called_once_with("emp-1", TEST_COMPANY_ID)
        mock_repo.create_on_demand.assert_called_once_with(
            TEST_COMPANY_ID, "emp-1", "Demande", "2025-03-17"
        )

    def test_get_me_flow_uses_repository_and_compute(self, client: TestClient):
        """GET /api/medical-follow-up/me : get_my_obligations_with_guards -> resolve_company, get_setting, my_obligations (repo.get_employee_id, compute, list_for_employee_no_join)."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_employee_id_by_user_id.return_value = "emp-1"
        mock_repo.list_for_employee_no_join.return_value = [
            {
                "id": "obl-me-1",
                "company_id": TEST_COMPANY_ID,
                "employee_id": "emp-1",
                "visit_type": "vip",
                "trigger_type": "periodicite_vip",
                "due_date": "2025-06-01",
                "priority": 1,
                "status": "a_faire",
                "rule_source": "legal",
            },
        ]

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with (
            patch(
                "app.modules.medical_follow_up.application.queries.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.commands.get_obligation_repository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
            patch(
                "app.modules.medical_follow_up.application.queries.compute_obligations_for_employee",
                return_value=[],
            ),
        ):
            response = client.get("/api/medical-follow-up/me")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "obl-me-1"
        mock_repo.get_employee_id_by_user_id.assert_called_once_with(
            str(TEST_USER_ID), TEST_COMPANY_ID
        )
        mock_repo.list_for_employee_no_join.assert_called_once_with(
            TEST_COMPANY_ID, "emp-1"
        )
