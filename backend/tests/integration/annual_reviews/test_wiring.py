"""
Tests de câblage (wiring) du module annual_reviews.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application -> repository / pdf generator) fonctionnent.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-wiring-test"
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


class TestAnnualReviewsWiring:
    """Flux complet : route -> commandes/queries -> repository."""

    def test_list_flow_uses_repository(self, client: TestClient):
        """GET /api/annual-reviews : le router appelle queries.list_all_annual_reviews qui utilise le repo."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.list_by_company.return_value = [
            {
                "id": "rev-1",
                "employee_id": "emp-1",
                "company_id": TEST_COMPANY_ID,
                "year": 2024,
                "status": "accepte",
                "planned_date": None,
                "completed_date": None,
                "created_at": "2024-01-01T00:00:00",
                "employees": {"first_name": "Jean", "last_name": "Dupont", "job_title": "Dev"},
            },
        ]

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch("app.modules.annual_reviews.application.service.get_repository", return_value=mock_repo):
            response = client.get("/api/annual-reviews")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "rev-1"
        assert data[0]["first_name"] == "Jean"
        assert data[0]["last_name"] == "Dupont"
        mock_repo.list_by_company.assert_called_once_with(TEST_COMPANY_ID, year=None, status=None)

    def test_create_flow_uses_repository(self, client: TestClient):
        """POST /api/annual-reviews : create_annual_review -> repo.get_employee_company_id + repo.create."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_employee_company_id.return_value = TEST_COMPANY_ID
        mock_repo.create.return_value = {
            "id": "rev-new",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "en_attente_acceptation",
            "planned_date": None,
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch("app.modules.annual_reviews.application.service.get_repository", return_value=mock_repo):
            response = client.post(
                "/api/annual-reviews",
                json={"employee_id": "emp-1", "year": 2024},
            )

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "rev-new"
        assert body["status"] == "en_attente_acceptation"
        mock_repo.get_employee_company_id.assert_called_once_with("emp-1")
        mock_repo.create.assert_called_once()
        call_data = mock_repo.create.call_args[0][0]
        assert call_data["employee_id"] == "emp-1"
        assert call_data["company_id"] == TEST_COMPANY_ID
        assert call_data["year"] == 2024

    def test_get_by_id_flow_uses_repository(self, client: TestClient):
        """GET /api/annual-reviews/{id} : get_annual_review_by_id -> repo.get_by_id."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = {
            "id": "rev-1",
            "employee_id": TEST_USER_ID,
            "company_id": TEST_COMPANY_ID,
            "year": 2024,
            "status": "accepte",
            "created_at": "2024-01-01T00:00:00",
            "updated_at": "2024-01-01T00:00:00",
        }

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch("app.modules.annual_reviews.application.service.get_repository", return_value=mock_repo):
            response = client.get("/api/annual-reviews/rev-1")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["id"] == "rev-1"
        mock_repo.get_by_id.assert_called_once_with("rev-1")

    def test_pdf_flow_uses_service_and_generator(self, client: TestClient):
        """GET /api/annual-reviews/{id}/pdf : service.generate_annual_review_pdf utilise repo + pdf_generator."""
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_employee_by_id.return_value = {
            "id": "emp-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Dev",
        }
        mock_repo.get_company_by_id.return_value = {"id": TEST_COMPANY_ID, "name": "Co"}

        mock_pdf_gen = MagicMock()
        mock_pdf_gen.generate.return_value = b"%PDF-1.4 fake"

        app.dependency_overrides[get_current_user] = lambda: _rh_user()
        with patch("app.modules.annual_reviews.application.service.get_repository", return_value=mock_repo), patch(
            "app.modules.annual_reviews.application.service.get_pdf_generator",
            return_value=mock_pdf_gen,
        ), patch(
            "app.modules.annual_reviews.application.queries.get_annual_review_for_pdf",
            return_value={
                "id": "rev-1",
                "company_id": TEST_COMPANY_ID,
                "employee_id": "emp-1",
                "year": 2024,
                "status": "cloture",
            },
        ):
            response = client.get("/api/annual-reviews/rev-1/pdf")

        app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.headers.get("content-type", "").startswith("application/pdf")
        assert b"%PDF" in response.content or response.content == b"%PDF-1.4 fake"
        mock_pdf_gen.generate.assert_called_once()
