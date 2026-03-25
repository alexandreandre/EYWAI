"""
Tests d'intégration HTTP des routes du module annual_reviews.

Préfixe des routes : /api/annual-reviews.
Utilise : client (TestClient). Pour les tests avec utilisateur authentifié,
dependency_overrides pour get_current_user et patch pour service.get_repository
(pas de JWT ni DB réels).
"""

from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

# IDs de test pour entreprise et utilisateur RH
TEST_COMPANY_ID = "company-annual-reviews-test"
TEST_RH_USER_ID = "user-rh-annual-reviews-test"


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
        id="user-emp-test",
        email="emp@test.com",
        first_name="Emp",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )
    return user


class TestAnnualReviewsUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_list_returns_401_without_auth(self, client: TestClient):
        """GET /api/annual-reviews sans auth → 401."""
        response = client.get("/api/annual-reviews")
        assert response.status_code == 401

    def test_get_by_employee_returns_401_without_auth(self, client: TestClient):
        """GET /api/annual-reviews/by-employee/{employee_id} sans auth → 401."""
        response = client.get("/api/annual-reviews/by-employee/emp-1")
        assert response.status_code == 401

    def test_get_me_returns_401_without_auth(self, client: TestClient):
        """GET /api/annual-reviews/me sans auth → 401."""
        response = client.get("/api/annual-reviews/me")
        assert response.status_code == 401

    def test_get_me_current_returns_401_without_auth(self, client: TestClient):
        """GET /api/annual-reviews/me/current sans auth → 401."""
        response = client.get("/api/annual-reviews/me/current")
        assert response.status_code == 401

    def test_get_by_id_returns_401_without_auth(self, client: TestClient):
        """GET /api/annual-reviews/{review_id} sans auth → 401."""
        response = client.get("/api/annual-reviews/rev-1")
        assert response.status_code == 401

    def test_post_create_returns_401_without_auth(self, client: TestClient):
        """POST /api/annual-reviews sans auth → 401."""
        response = client.post(
            "/api/annual-reviews",
            json={"employee_id": "emp-1", "year": 2024},
        )
        assert response.status_code == 401

    def test_put_update_returns_401_without_auth(self, client: TestClient):
        """PUT /api/annual-reviews/{review_id} sans auth → 401."""
        response = client.put(
            "/api/annual-reviews/rev-1",
            json={"status": "accepte"},
        )
        assert response.status_code == 401

    def test_post_mark_completed_returns_401_without_auth(self, client: TestClient):
        """POST /api/annual-reviews/{review_id}/mark-completed sans auth → 401."""
        response = client.post("/api/annual-reviews/rev-1/mark-completed")
        assert response.status_code == 401

    def test_get_pdf_returns_401_without_auth(self, client: TestClient):
        """GET /api/annual-reviews/{review_id}/pdf sans auth → 401."""
        response = client.get("/api/annual-reviews/rev-1/pdf")
        assert response.status_code == 401

    def test_delete_returns_401_without_auth(self, client: TestClient):
        """DELETE /api/annual-reviews/{review_id} sans auth → 401."""
        response = client.delete("/api/annual-reviews/rev-1")
        assert response.status_code == 401


class TestAnnualReviewsWithRhUser:
    """Avec utilisateur RH injecté (dependency_overrides) et repository mocké."""

    @pytest.fixture
    def mock_repo(self):
        """Repository mock : listes vides, get_by_id None par défaut."""
        repo = MagicMock()
        repo.list_by_company.return_value = []
        repo.get_by_id.return_value = None
        repo.list_by_employee.return_value = []
        repo.get_my_current.return_value = None
        repo.get_employee_company_id.return_value = TEST_COMPANY_ID
        repo.get_employee_by_id.return_value = {
            "id": "emp-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Dev",
        }
        repo.get_company_by_id.return_value = {"id": TEST_COMPANY_ID, "name": "Test Co"}
        repo.create.return_value = {
            "id": "rev-new",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "en_attente_acceptation",
            "planned_date": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        repo.update.return_value = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "accepte",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        return repo

    @pytest.fixture
    def client_with_rh(self, client: TestClient, mock_repo):
        """Client avec get_current_user overridé et get_repository patché (router appelle service.get_repository())."""
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
        with patch(
            "app.modules.annual_reviews.application.service.get_repository",
            return_value=mock_repo,
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_list_returns_200_and_list(self, client_with_rh: TestClient):
        """GET /api/annual-reviews en tant que RH → 200 et liste (vide ou non)."""
        response = client_with_rh.get("/api/annual-reviews")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_list_accepts_query_params(self, client_with_rh: TestClient, mock_repo):
        """GET /api/annual-reviews?year=2024&status=accepte transmet les filtres."""
        client_with_rh.get("/api/annual-reviews?year=2024&status=accepte")
        mock_repo.list_by_company.assert_called_once()
        call_kw = mock_repo.list_by_company.call_args[1]
        assert call_kw.get("year") == 2024
        assert call_kw.get("status") == "accepte"

    def test_get_by_employee_returns_200_and_list(self, client_with_rh: TestClient):
        """GET /api/annual-reviews/by-employee/{employee_id} en RH → 200."""
        response = client_with_rh.get("/api/annual-reviews/by-employee/emp-1")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_me_returns_200(self, client_with_rh: TestClient):
        """GET /api/annual-reviews/me → 200."""
        response = client_with_rh.get("/api/annual-reviews/me")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_me_current_returns_200_or_null(self, client_with_rh: TestClient):
        """GET /api/annual-reviews/me/current → 200 (body peut être null)."""
        response = client_with_rh.get("/api/annual-reviews/me/current")
        assert response.status_code == 200

    def test_get_by_id_returns_404_when_not_found(self, client_with_rh: TestClient):
        """GET /api/annual-reviews/{id} quand entretien inexistant → 404."""
        response = client_with_rh.get("/api/annual-reviews/rev-unknown")
        assert response.status_code == 404
        assert (
            "Entretien" in response.json().get("detail", "")
            or "trouvé" in response.json().get("detail", "").lower()
        )

    def test_get_by_id_returns_200_when_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET /api/annual-reviews/{id} quand entretien trouvé → 200."""
        mock_repo.get_by_id.return_value = {
            "id": "rev-1",
            "employee_id": TEST_RH_USER_ID,
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "accepte",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }
        response = client_with_rh.get("/api/annual-reviews/rev-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "rev-1"
        assert data["year"] == 2024

    def test_post_create_returns_201(self, client_with_rh: TestClient, mock_repo):
        """POST /api/annual-reviews avec employee_id et year → 201."""
        response = client_with_rh.post(
            "/api/annual-reviews",
            json={
                "employee_id": "emp-1",
                "year": 2024,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["employee_id"] == "emp-1"
        assert data["year"] == 2024
        assert data["status"] == "en_attente_acceptation"
        mock_repo.create.assert_called_once()

    def test_post_create_without_employee_id_returns_400(
        self, client_with_rh: TestClient
    ):
        """POST /api/annual-reviews sans employee_id → 400 (validation ou métier)."""
        response = client_with_rh.post(
            "/api/annual-reviews",
            json={"year": 2024},
        )
        assert response.status_code in (400, 422)

    def test_put_update_returns_404_when_not_found(self, client_with_rh: TestClient):
        """PUT /api/annual-reviews/{id} quand entretien inexistant → 404."""
        response = client_with_rh.put(
            "/api/annual-reviews/rev-unknown",
            json={"status": "accepte"},
        )
        assert response.status_code == 404

    def test_put_update_returns_200_when_found(
        self, client_with_rh: TestClient, mock_repo
    ):
        """PUT /api/annual-reviews/{id} avec données valides → 200."""
        mock_repo.get_by_id.return_value = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "status": "realise",
        }
        response = client_with_rh.put(
            "/api/annual-reviews/rev-1",
            json={"meeting_report": "Compte-rendu"},
        )
        assert response.status_code == 200
        mock_repo.update.assert_called_once()

    def test_post_mark_completed_returns_404_when_not_found(
        self, client_with_rh: TestClient
    ):
        """POST .../mark-completed quand entretien inexistant → 404."""
        response = client_with_rh.post("/api/annual-reviews/rev-unknown/mark-completed")
        assert response.status_code == 404

    def test_post_mark_completed_returns_200_when_accepte(
        self, client_with_rh: TestClient, mock_repo
    ):
        """POST .../mark-completed quand status=accepte → 200."""
        mock_repo.get_by_id.return_value = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "accepte",
        }
        mock_repo.update.return_value = {
            "id": "rev-1",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "realise",
            "completed_date": date.today().isoformat(),
            "created_at": "2024-01-01T00:00:00",
            "updated_at": datetime.utcnow().isoformat(),
        }
        response = client_with_rh.post("/api/annual-reviews/rev-1/mark-completed")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "realise"

    def test_get_pdf_returns_404_when_not_found(self, client_with_rh: TestClient):
        """GET .../pdf quand entretien inexistant → 404."""
        response = client_with_rh.get("/api/annual-reviews/rev-unknown/pdf")
        assert response.status_code == 404

    def test_get_pdf_returns_400_when_not_cloture(
        self, client_with_rh: TestClient, mock_repo
    ):
        """GET .../pdf quand entretien non clôturé → 400."""
        mock_repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": TEST_COMPANY_ID,
            "employee_id": "emp-1",
            "status": "realise",
        }
        response = client_with_rh.get("/api/annual-reviews/rev-1/pdf")
        assert response.status_code == 400
        assert "clôturé" in response.json().get(
            "detail", ""
        ) or "PDF" in response.json().get("detail", "")

    def test_delete_returns_404_when_not_found(self, client_with_rh: TestClient):
        """DELETE /api/annual-reviews/{id} quand entretien inexistant → 404."""
        response = client_with_rh.delete("/api/annual-reviews/rev-unknown")
        assert response.status_code == 404

    def test_delete_returns_204_when_found(self, client_with_rh: TestClient, mock_repo):
        """DELETE /api/annual-reviews/{id} quand entretien trouvé → 204."""
        mock_repo.get_by_id.return_value = {
            "id": "rev-1",
            "company_id": TEST_COMPANY_ID,
        }
        response = client_with_rh.delete("/api/annual-reviews/rev-1")
        assert response.status_code == 204
        mock_repo.delete.assert_called_once_with("rev-1")


class TestAnnualReviewsForbiddenNonRh:
    """Utilisateur authentifié sans droits RH : 403 sur les routes RH."""

    @pytest.fixture
    def mock_repo(self):
        repo = MagicMock()
        repo.list_by_company.return_value = []
        repo.get_by_id.return_value = None
        repo.list_by_employee.return_value = []
        repo.get_my_current.return_value = None
        return repo

    @pytest.fixture
    def client_with_employee(self, client: TestClient, mock_repo):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
        with patch(
            "app.modules.annual_reviews.application.service.get_repository",
            return_value=mock_repo,
        ):
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    def test_get_list_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """GET /api/annual-reviews en tant que collaborateur → 403."""
        response = client_with_employee.get("/api/annual-reviews")
        assert response.status_code == 403
        assert "Accès réservé" in response.json().get(
            "detail", ""
        ) or "RH" in response.json().get("detail", "")

    def test_get_by_employee_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """GET /api/annual-reviews/by-employee/{id} en tant que collaborateur → 403."""
        response = client_with_employee.get("/api/annual-reviews/by-employee/emp-1")
        assert response.status_code == 403

    def test_post_create_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """POST /api/annual-reviews en tant que collaborateur → 403."""
        response = client_with_employee.post(
            "/api/annual-reviews",
            json={"employee_id": "emp-1", "year": 2024},
        )
        assert response.status_code == 403

    def test_post_mark_completed_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """POST .../mark-completed en tant que collaborateur → 403."""
        response = client_with_employee.post("/api/annual-reviews/rev-1/mark-completed")
        assert response.status_code == 403

    def test_delete_returns_403_for_collaborator(
        self, client_with_employee: TestClient
    ):
        """DELETE /api/annual-reviews/{id} en tant que collaborateur → 403."""
        response = client_with_employee.delete("/api/annual-reviews/rev-1")
        assert response.status_code == 403
