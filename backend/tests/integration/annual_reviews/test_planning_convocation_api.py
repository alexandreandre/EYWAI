"""Smoke HTTP : planning-suggestions et convocation-pdf."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from tests.integration.annual_reviews.test_api import TEST_COMPANY_ID, _make_employee_user, _make_rh_user

pytestmark = pytest.mark.integration


@pytest.fixture
def rh_client():
    app.dependency_overrides[get_current_user] = _make_rh_user
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def emp_client():
    app.dependency_overrides[get_current_user] = _make_employee_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_planning_suggestions_unauthenticated(client: TestClient):
    assert client.get("/api/annual-reviews/planning-suggestions").status_code == 401


def test_convocation_unauthenticated(client: TestClient):
    assert client.get("/api/annual-reviews/rev-1/convocation-pdf").status_code == 401


def test_planning_suggestions_employee_forbidden(emp_client: TestClient):
    assert emp_client.get("/api/annual-reviews/planning-suggestions").status_code == 403


def test_planning_suggestions_rh_returns_list(rh_client: TestClient):
    employees = [
        {
            "id": "e1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "statut": "Cadre au forfait jour",
            "employment_status": "actif",
        }
    ]
    with patch(
        "app.modules.annual_reviews.infrastructure.queries.query_list_active_employees",
        return_value=employees,
    ), patch(
        "app.modules.annual_reviews.infrastructure.queries.query_reviews_for_company_year",
        return_value=[],
    ):
        r = rh_client.get("/api/annual-reviews/planning-suggestions?year=2026")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    types = {item["interview_type"] for item in data}
    assert types == {"annual_forfait_jour", "annual_cadres"}


def test_convocation_pdf_rh_returns_pdf(rh_client: TestClient):
    review_row = {
        "id": "rev1",
        "company_id": TEST_COMPANY_ID,
        "employee_id": "e1",
        "status": "en_attente_acceptation",
        "interview_type": "annual_cadres",
        "planned_date": "2026-06-15",
        "year": 2026,
    }
    with patch(
        "app.modules.annual_reviews.application.service.get_repository"
    ) as get_repo:
        repo = get_repo.return_value
        repo.get_by_id.return_value = review_row
        repo.get_employee_by_id.return_value = {
            "first_name": "Jean",
            "last_name": "Dupont",
            "job_title": "Ingénieur",
        }
        repo.get_company_by_id.return_value = {
            "company_name": "Test Co",
            "nom_signataire_rh": "DG Test",
            "qualite_signataire_rh": "Directeur Général",
        }
        r = rh_client.get("/api/annual-reviews/rev1/convocation-pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"
