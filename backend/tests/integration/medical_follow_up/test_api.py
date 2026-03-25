"""
Tests d'intégration HTTP des routes du module medical_follow_up.

Préfixe des routes : /api/medical-follow-up.
Utilise : client (TestClient). Pour les tests avec utilisateur authentifié,
dependency_overrides pour get_current_user et patch pour get_obligation_repository
et get_settings_provider (pas de JWT ni DB réels).
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-medical-follow-up-test"
TEST_RH_USER_ID = "user-rh-medical-test"


def _make_rh_user():
    """Utilisateur de test avec droits RH sur TEST_COMPANY_ID et active_company_id renseigné."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    user = User(
        id=TEST_RH_USER_ID,
        email="rh@test.com",
        first_name="RH",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )
    return user


def _make_employee_user():
    """Utilisateur de test sans droits RH (collaborateur)."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur",
        is_primary=True,
    )
    user = User(
        id="user-emp-medical-test",
        email="emp@test.com",
        first_name="Emp",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )
    return user


class TestMedicalFollowUpUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_obligations_returns_401_without_auth(self, client: TestClient):
        """GET /api/medical-follow-up/obligations sans auth → 401."""
        response = client.get("/api/medical-follow-up/obligations")
        assert response.status_code == 401

    def test_get_kpis_returns_401_without_auth(self, client: TestClient):
        """GET /api/medical-follow-up/kpis sans auth → 401."""
        response = client.get("/api/medical-follow-up/kpis")
        assert response.status_code == 401

    def test_patch_planified_returns_401_without_auth(self, client: TestClient):
        """PATCH .../obligations/{id}/planified sans auth → 401."""
        response = client.patch(
            "/api/medical-follow-up/obligations/obl-1/planified",
            json={"planned_date": "2025-04-15"},
        )
        assert response.status_code == 401

    def test_patch_completed_returns_401_without_auth(self, client: TestClient):
        """PATCH .../obligations/{id}/completed sans auth → 401."""
        response = client.patch(
            "/api/medical-follow-up/obligations/obl-1/completed",
            json={"completed_date": "2025-04-20"},
        )
        assert response.status_code == 401

    def test_post_on_demand_returns_401_without_auth(self, client: TestClient):
        """POST /api/medical-follow-up/obligations/on-demand sans auth → 401."""
        response = client.post(
            "/api/medical-follow-up/obligations/on-demand",
            json={
                "employee_id": "emp-1",
                "request_motif": "Demande",
                "request_date": "2025-03-17",
            },
        )
        assert response.status_code == 401

    def test_get_employee_obligations_returns_401_without_auth(
        self, client: TestClient
    ):
        """GET .../obligations/employee/{employee_id} sans auth → 401."""
        response = client.get("/api/medical-follow-up/obligations/employee/emp-1")
        assert response.status_code == 401

    def test_get_me_returns_401_without_auth(self, client: TestClient):
        """GET /api/medical-follow-up/me sans auth → 401."""
        response = client.get("/api/medical-follow-up/me")
        assert response.status_code == 401

    def test_get_settings_returns_401_without_auth(self, client: TestClient):
        """GET /api/medical-follow-up/settings sans auth → 401."""
        response = client.get("/api/medical-follow-up/settings")
        assert response.status_code == 401


class TestMedicalFollowUpWithRhUser:
    """Avec utilisateur RH injecté (dependency_overrides) et repository / settings mockés."""

    @pytest.fixture
    def mock_repo(self):
        """Repository mock : listes, KPIs, obligation_exists, employee_exists, etc."""
        repo = MagicMock()
        repo.list_for_company.return_value = []
        repo.get_kpis.return_value = {
            "overdue_count": 0,
            "due_within_30_count": 0,
            "active_total": 0,
            "completed_this_month": 0,
        }
        repo.obligation_exists.return_value = True
        repo.employee_exists.return_value = True
        repo.get_employee_id_by_user_id.return_value = "emp-1"
        repo.list_for_employee.return_value = []
        repo.list_for_employee_no_join.return_value = []
        return repo

    @pytest.fixture
    def client_with_rh(self, client: TestClient, mock_repo):
        """Client avec get_current_user overridé, get_obligation_repository et get_settings_provider patchés."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
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
                "app.modules.medical_follow_up.application.queries.compute_obligations_for_employee",
                return_value=[],
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_obligations_returns_200_and_list(self, client_with_rh: TestClient):
        """GET /api/medical-follow-up/obligations en tant que RH → 200 et liste."""
        response = client_with_rh.get("/api/medical-follow-up/obligations")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_obligations_accepts_query_params(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET /api/medical-follow-up/obligations?employee_id=emp-1 transmet les filtres."""
        client_with_rh.get(
            "/api/medical-follow-up/obligations?employee_id=emp-1&visit_type=vip&status=a_faire"
        )
        mock_repo.list_for_company.assert_called_once()
        call_kw = mock_repo.list_for_company.call_args[1]
        assert call_kw.get("employee_id") == "emp-1"
        assert call_kw.get("visit_type") == "vip"
        assert call_kw.get("status") == "a_faire"

    def test_get_kpis_returns_200_and_kpis(self, client_with_rh: TestClient, mock_repo):
        """GET /api/medical-follow-up/kpis → 200 et KPIs."""
        mock_repo.get_kpis.return_value = {
            "overdue_count": 2,
            "due_within_30_count": 3,
            "active_total": 5,
            "completed_this_month": 1,
        }
        response = client_with_rh.get("/api/medical-follow-up/kpis")
        assert response.status_code == 200
        data = response.json()
        assert data["overdue_count"] == 2
        assert data["due_within_30_count"] == 3
        assert data["active_total"] == 5
        assert data["completed_this_month"] == 1

    def test_patch_planified_returns_200(self, client_with_rh: TestClient, mock_repo):
        """PATCH .../obligations/{id}/planified → 200."""
        response = client_with_rh.patch(
            "/api/medical-follow-up/obligations/obl-1/planified",
            json={"planned_date": "2025-04-15", "justification": "RDV fixé"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_repo.mark_planified.assert_called_once()

    def test_patch_planified_returns_404_when_obligation_not_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """PATCH .../planified quand obligation inexistante → 404."""
        mock_repo.obligation_exists.return_value = False
        response = client_with_rh.patch(
            "/api/medical-follow-up/obligations/obl-unknown/planified",
            json={"planned_date": "2025-04-15"},
        )
        assert response.status_code == 404
        assert "Obligation" in response.json().get(
            "detail", ""
        ) or "trouvée" in response.json().get("detail", "")

    def test_patch_completed_returns_200(self, client_with_rh: TestClient, mock_repo):
        """PATCH .../obligations/{id}/completed → 200."""
        response = client_with_rh.patch(
            "/api/medical-follow-up/obligations/obl-1/completed",
            json={"completed_date": "2025-04-20", "justification": "Visite effectuée"},
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_repo.mark_completed.assert_called_once()

    def test_patch_completed_returns_404_when_obligation_not_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """PATCH .../completed quand obligation inexistante → 404."""
        mock_repo.obligation_exists.return_value = False
        response = client_with_rh.patch(
            "/api/medical-follow-up/obligations/obl-unknown/completed",
            json={"completed_date": "2025-04-20"},
        )
        assert response.status_code == 404

    def test_post_on_demand_returns_200(self, client_with_rh: TestClient, mock_repo):
        """POST /api/medical-follow-up/obligations/on-demand → 200."""
        response = client_with_rh.post(
            "/api/medical-follow-up/obligations/on-demand",
            json={
                "employee_id": "emp-1",
                "request_motif": "Demande du salarié",
                "request_date": "2025-03-17",
            },
        )
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        mock_repo.create_on_demand.assert_called_once()

    def test_post_on_demand_returns_404_when_employee_not_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """POST .../on-demand quand salarié inexistant → 404."""
        mock_repo.employee_exists.return_value = False
        response = client_with_rh.post(
            "/api/medical-follow-up/obligations/on-demand",
            json={
                "employee_id": "emp-unknown",
                "request_motif": "Motif",
                "request_date": "2025-03-17",
            },
        )
        assert response.status_code == 404
        assert "Salarié" in response.json().get(
            "detail", ""
        ) or "trouvé" in response.json().get("detail", "")

    def test_get_employee_obligations_returns_200(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET .../obligations/employee/{employee_id} → 200."""
        mock_repo.list_for_employee.return_value = [
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
        response = client_with_rh.get(
            "/api/medical-follow-up/obligations/employee/emp-1"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "obl-1"

    def test_get_employee_obligations_returns_404_when_employee_not_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET .../obligations/employee/{id} quand salarié inexistant → 404."""
        mock_repo.employee_exists.return_value = False
        response = client_with_rh.get(
            "/api/medical-follow-up/obligations/employee/emp-unknown"
        )
        assert response.status_code == 404

    def test_get_me_returns_200(self, client_with_rh: TestClient, mock_repo):
        """GET /api/medical-follow-up/me → 200 (obligations du collaborateur connecté)."""
        response = client_with_rh.get("/api/medical-follow-up/me")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_me_returns_404_when_no_employee_profile(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET /me quand pas de profil collaborateur (user sans employé) → 404."""
        mock_repo.get_employee_id_by_user_id.return_value = None
        response = client_with_rh.get("/api/medical-follow-up/me")
        assert response.status_code == 404
        assert "Profil" in response.json().get(
            "detail", ""
        ) or "trouvé" in response.json().get("detail", "")

    def test_get_settings_returns_200(self, client_with_rh: TestClient):
        """GET /api/medical-follow-up/settings → 200 et enabled."""
        response = client_with_rh.get("/api/medical-follow-up/settings")
        assert response.status_code == 200
        data = response.json()
        assert "enabled" in data
        assert data["enabled"] is True


class TestMedicalFollowUpForbiddenNonRh:
    """Utilisateur authentifié sans droits RH : 403 sur les routes RH."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.list_for_company.return_value = []
        repo.get_kpis.return_value = {}
        repo.obligation_exists.return_value = True
        repo.employee_exists.return_value = True
        return repo

    @pytest.fixture
    def client_with_employee(self, client: TestClient, mock_repo):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
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
                "app.modules.medical_follow_up.application.queries.compute_obligations_for_employee",
                return_value=[],
            ),
            patch(
                "app.modules.medical_follow_up.application.service.get_settings_provider",
                return_value=MagicMock(is_enabled=MagicMock(return_value=True)),
            ),
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_obligations_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """GET /api/medical-follow-up/obligations en tant que collaborateur → 403."""
        response = client_with_employee.get("/api/medical-follow-up/obligations")
        assert response.status_code == 403
        assert "Accès" in response.json().get(
            "detail", ""
        ) or "autorisé" in response.json().get("detail", "")

    def test_get_kpis_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """GET /api/medical-follow-up/kpis en tant que collaborateur → 403."""
        response = client_with_employee.get("/api/medical-follow-up/kpis")
        assert response.status_code == 403

    def test_patch_planified_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """PATCH .../planified en tant que collaborateur → 403."""
        response = client_with_employee.patch(
            "/api/medical-follow-up/obligations/obl-1/planified",
            json={"planned_date": "2025-04-15"},
        )
        assert response.status_code == 403

    def test_post_on_demand_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """POST .../on-demand en tant que collaborateur → 403."""
        response = client_with_employee.post(
            "/api/medical-follow-up/obligations/on-demand",
            json={
                "employee_id": "emp-1",
                "request_motif": "Demande",
                "request_date": "2025-03-17",
            },
        )
        assert response.status_code == 403

    def test_get_employee_obligations_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """GET .../obligations/employee/{id} en tant que collaborateur → 403."""
        response = client_with_employee.get(
            "/api/medical-follow-up/obligations/employee/emp-1"
        )
        assert response.status_code == 403
