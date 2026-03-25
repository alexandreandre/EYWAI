"""
Tests d'intégration HTTP des routes du module employee_exits.

Préfixe des routes : /api/employee-exits.
Utilise : client (TestClient, conftest.py). Pour les tests authentifiés,
dependency_overrides pour get_current_user et patch des commands/queries
(pas de JWT ni DB réels).

Fixture optionnelle à ajouter dans conftest.py si besoin de tests E2E avec token réel :
  @pytest.fixture
  def employee_exits_headers(auth_headers):
      \"\"\"En-têtes pour un utilisateur avec active_company_id et droits RH (admin/rh).
      Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.\"\"\"
      return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
"""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import CompanyAccess, User


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-employee-exits-test"
TEST_RH_USER_ID = "user-rh-employee-exits-test"
EXIT_ID = "exit-api-test-uuid"
EMPLOYEE_ID = "employee-api-test-uuid"


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


def _make_exit_response():
    return {
        "id": EXIT_ID,
        "company_id": TEST_COMPANY_ID,
        "employee_id": EMPLOYEE_ID,
        "exit_type": "demission",
        "status": "demission_recue",
        "exit_request_date": "2025-01-15",
        "last_working_day": "2025-03-15",
        "notice_period_days": 60,
        "is_gross_misconduct": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


class TestEmployeeExitsUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_list_returns_401_without_auth(self, client: TestClient):
        """GET /api/employee-exits sans auth → 401."""
        response = client.get("/api/employee-exits")
        assert response.status_code == 401

    def test_get_by_id_returns_401_without_auth(self, client: TestClient):
        """GET /api/employee-exits/{exit_id} sans auth → 401."""
        response = client.get(f"/api/employee-exits/{EXIT_ID}")
        assert response.status_code == 401

    def test_post_create_returns_401_without_auth(self, client: TestClient):
        """POST /api/employee-exits sans auth → 401."""
        response = client.post(
            "/api/employee-exits",
            json={
                "employee_id": str(EMPLOYEE_ID),
                "exit_type": "demission",
                "exit_request_date": "2025-01-15",
                "last_working_day": "2025-03-15",
            },
        )
        assert response.status_code == 401

    def test_patch_returns_401_without_auth(self, client: TestClient):
        """PATCH /api/employee-exits/{exit_id} sans auth → 401."""
        response = client.patch(f"/api/employee-exits/{EXIT_ID}", json={"exit_reason": "Test"})
        assert response.status_code == 401

    def test_patch_status_returns_401_without_auth(self, client: TestClient):
        """PATCH /api/employee-exits/{exit_id}/status sans auth → 401."""
        response = client.patch(
            f"/api/employee-exits/{EXIT_ID}/status",
            json={"new_status": "demission_effective"},
        )
        assert response.status_code == 401

    def test_delete_returns_401_without_auth(self, client: TestClient):
        """DELETE /api/employee-exits/{exit_id} sans auth → 401."""
        response = client.delete(f"/api/employee-exits/{EXIT_ID}")
        assert response.status_code == 401

    def test_post_calculate_indemnities_returns_401_without_auth(self, client: TestClient):
        """POST /api/employee-exits/{exit_id}/calculate-indemnities sans auth → 401."""
        response = client.post(f"/api/employee-exits/{EXIT_ID}/calculate-indemnities")
        assert response.status_code == 401

    def test_get_documents_returns_401_without_auth(self, client: TestClient):
        """GET /api/employee-exits/{exit_id}/documents sans auth → 401."""
        response = client.get(f"/api/employee-exits/{EXIT_ID}/documents")
        assert response.status_code == 401

    def test_get_checklist_returns_401_without_auth(self, client: TestClient):
        """GET /api/employee-exits/{exit_id}/checklist sans auth → 401."""
        response = client.get(f"/api/employee-exits/{EXIT_ID}/checklist")
        assert response.status_code == 401


class TestEmployeeExitsWithRhUser:
    """Avec utilisateur RH injecté (dependency_overrides) et commands/queries mockés."""

    @pytest.fixture
    def client_with_rh(self, client: TestClient):
        """Client avec get_current_user overridé."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        try:
            yield client
        finally:
            app.dependency_overrides.pop(get_current_user, None)

    def test_get_list_returns_200_and_list(self, client_with_rh: TestClient):
        """GET /api/employee-exits en tant que RH → 200 et liste."""
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.list_employee_exits.return_value = []
            response = client_with_rh.get("/api/employee-exits")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_list_with_filters(self, client_with_rh: TestClient):
        """GET /api/employee-exits?status=...&exit_type=... transmet les filtres."""
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.list_employee_exits.return_value = []
            client_with_rh.get("/api/employee-exits?status=demission_effective&exit_type=demission")
            mock_queries.list_employee_exits.assert_called_once()
            call_kw = mock_queries.list_employee_exits.call_args[1]
            assert call_kw.get("status") == "demission_effective"
            assert call_kw.get("exit_type") == "demission"

    def test_get_by_id_returns_200_when_found(self, client_with_rh: TestClient):
        """GET /api/employee-exits/{exit_id} quand sortie trouvée → 200."""
        exit_data = _make_exit_response()
        exit_data["documents"] = []
        exit_data["checklist_items"] = []
        exit_data["checklist_completion_rate"] = 0.0
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.get_employee_exit.return_value = exit_data
            response = client_with_rh.get(f"/api/employee-exits/{EXIT_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == EXIT_ID
        assert data["exit_type"] == "demission"

    def test_get_by_id_returns_404_when_not_found(self, client_with_rh: TestClient):
        """GET /api/employee-exits/{exit_id} quand sortie inexistante → 404."""
        from app.modules.employee_exits.application.dto import EmployeeExitApplicationError

        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.get_employee_exit.side_effect = EmployeeExitApplicationError(404, "Sortie non trouvée")
            response = client_with_rh.get(f"/api/employee-exits/{EXIT_ID}")
        assert response.status_code == 404

    def test_post_create_returns_201(self, client_with_rh: TestClient):
        """POST /api/employee-exits avec payload valide → 201."""
        with patch("app.modules.employee_exits.api.router.queries.get_employee_company_id", return_value=TEST_COMPANY_ID):
            with patch("app.modules.employee_exits.api.router.commands") as mock_commands:
                created = _make_exit_response()
                mock_commands.create_employee_exit.return_value = created
                response = client_with_rh.post(
                    "/api/employee-exits",
                    json={
                        "employee_id": str(EMPLOYEE_ID),
                        "exit_type": "demission",
                        "exit_request_date": "2025-01-15",
                        "last_working_day": "2025-03-15",
                        "notice_period_days": 60,
                    },
                )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == EXIT_ID
        assert data["employee_id"] == str(EMPLOYEE_ID)

    def test_post_create_without_employee_id_returns_422(self, client_with_rh: TestClient):
        """POST /api/employee-exits sans employee_id → 422 (validation)."""
        response = client_with_rh.post(
            "/api/employee-exits",
            json={
                "exit_type": "demission",
                "exit_request_date": "2025-01-15",
                "last_working_day": "2025-03-15",
            },
        )
        assert response.status_code == 422

    def test_patch_returns_200_when_found(self, client_with_rh: TestClient):
        """PATCH /api/employee-exits/{exit_id} avec données valides → 200."""
        updated = _make_exit_response()
        updated["exit_reason"] = "Nouvelle raison"
        with patch("app.modules.employee_exits.api.router.commands") as mock_commands:
            mock_commands.update_employee_exit.return_value = updated
            response = client_with_rh.patch(
                f"/api/employee-exits/{EXIT_ID}",
                json={"exit_reason": "Nouvelle raison"},
            )
        assert response.status_code == 200
        assert response.json()["exit_reason"] == "Nouvelle raison"

    def test_patch_status_returns_200(self, client_with_rh: TestClient):
        """PATCH /api/employee-exits/{exit_id}/status → 200."""
        updated = _make_exit_response()
        updated["status"] = "demission_preavis_en_cours"
        with patch("app.modules.employee_exits.api.router.commands") as mock_commands:
            mock_commands.update_exit_status.return_value = updated
            response = client_with_rh.patch(
                f"/api/employee-exits/{EXIT_ID}/status",
                json={"new_status": "demission_preavis_en_cours"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data.get("exit", {}).get("status") == "demission_preavis_en_cours"

    def test_delete_returns_204(self, client_with_rh: TestClient):
        """DELETE /api/employee-exits/{exit_id} → 204."""
        with patch("app.modules.employee_exits.api.router.commands") as mock_commands:
            mock_commands.delete_employee_exit.return_value = None
            response = client_with_rh.delete(f"/api/employee-exits/{EXIT_ID}")
        assert response.status_code == 204

    def test_post_calculate_indemnities_returns_200(self, client_with_rh: TestClient):
        """POST /api/employee-exits/{exit_id}/calculate-indemnities → 200."""
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.calculate_exit_indemnities.return_value = {
                "total_gross_indemnities": 5000,
                "total_net_indemnities": 4000,
                "indemnite_conges": {},
            }
            response = client_with_rh.post(f"/api/employee-exits/{EXIT_ID}/calculate-indemnities")
        assert response.status_code == 200

    def test_get_documents_returns_200(self, client_with_rh: TestClient):
        """GET /api/employee-exits/{exit_id}/documents → 200."""
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.list_exit_documents.return_value = []
            response = client_with_rh.get(f"/api/employee-exits/{EXIT_ID}/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_checklist_returns_200(self, client_with_rh: TestClient):
        """GET /api/employee-exits/{exit_id}/checklist → 200."""
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.get_exit_checklist.return_value = []
            response = client_with_rh.get(f"/api/employee-exits/{EXIT_ID}/checklist")
        assert response.status_code == 200
        assert response.json() == []

    def test_post_upload_url_returns_200(self, client_with_rh: TestClient):
        """POST /api/employee-exits/{exit_id}/documents/upload-url → 200."""
        with patch("app.modules.employee_exits.api.router.queries") as mock_queries:
            mock_queries.get_document_upload_url.return_value = {
                "upload_url": "https://upload.example/url",
                "storage_path": "exits/1/file.pdf",
                "expires_in": 3600,
            }
            response = client_with_rh.post(
                f"/api/employee-exits/{EXIT_ID}/documents/upload-url",
                json={"filename": "file.pdf"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert data["expires_in"] == 3600
