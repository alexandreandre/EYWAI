"""
Tests d'intégration HTTP des routes du module recruitment.

Routes : GET/POST/PATCH /api/recruitment/jobs, GET /api/recruitment/jobs/{id}/stages,
GET/POST/PATCH/DELETE /api/recruitment/candidates, POST move, check-duplicate, hire,
GET/POST /api/recruitment/interviews, PATCH /api/recruitment/interviews/{id},
GET/POST /api/recruitment/notes, GET/POST /api/recruitment/opinions,
GET /api/recruitment/timeline, GET /api/recruitment/rejection-reasons, GET /api/recruitment/settings.

Utilise : client (TestClient), dependency_overrides pour get_current_user.
Les commandes et queries sont mockées pour éviter la DB réelle (comportement identique
aux autres modules : bonus_types, annual_reviews).

Fixture à ajouter dans conftest.py pour tests E2E avec JWT réel :
  @pytest.fixture
  def recruitment_headers(auth_headers):
      \"\"\"En-têtes pour un utilisateur avec active_company_id et droits RH sur le module
      Recrutement. Format : {\"Authorization\": \"Bearer <jwt>\", \"X-Active-Company\": \"<company_id>\"}.\"\"\"
      return auth_headers  # ou return {**auth_headers, "X-Active-Company": "<company_uuid>"}
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_RH_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_RH_USER_ID):
    """Utilisateur de test avec droits RH et entreprise active (module recrutement)."""
    return User(
        id=user_id,
        email="rh@recruitment-test.com",
        first_name="RH",
        last_name="Recruitment",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


@pytest.fixture
def recruitment_client(client: TestClient):
    """Client avec get_current_user overridé pour retourner un utilisateur RH avec company."""

    def _get_current_user_override():
        return _make_rh_user()

    app.dependency_overrides[get_current_user] = _get_current_user_override
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


# ─── Sans auth ─────────────────────────────────────────────────────────


class TestRecruitmentUnauthenticated:
    """Sans token : routes protégées renvoient 401."""

    def test_get_settings_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/recruitment/settings")
        assert response.status_code == 401

    def test_list_jobs_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/recruitment/jobs")
        assert response.status_code == 401

    def test_create_job_returns_401_without_auth(self, client: TestClient):
        response = client.post(
            "/api/recruitment/jobs",
            json={"title": "Dev", "status": "draft"},
        )
        assert response.status_code == 401

    def test_list_candidates_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/recruitment/candidates")
        assert response.status_code == 401

    def test_get_rejection_reasons_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/recruitment/rejection-reasons")
        assert response.status_code == 401


# ─── Settings ───────────────────────────────────────────────────────────


class TestRecruitmentSettings:
    """GET /api/recruitment/settings."""

    def test_returns_enabled_with_auth(self, recruitment_client: TestClient):
        with patch(
            "app.modules.recruitment.api.router.queries.get_recruitment_settings"
        ) as m:
            m.return_value = {"enabled": True}
            response = recruitment_client.get("/api/recruitment/settings")
        assert response.status_code == 200
        assert response.json() == {"enabled": True}


# ─── Jobs ──────────────────────────────────────────────────────────────


class TestRecruitmentJobs:
    """GET/POST/PATCH /api/recruitment/jobs."""

    def test_list_jobs_returns_200_and_list(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.list_jobs") as m:
            m.return_value = [
                {
                    "id": "j1",
                    "company_id": TEST_COMPANY_ID,
                    "title": "Dev",
                    "status": "draft",
                    "candidate_count": 0,
                    "created_at": "",
                    "updated_at": "",
                },
            ]
            response = recruitment_client.get("/api/recruitment/jobs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["title"] == "Dev"

    def test_create_job_returns_201_and_job(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_job") as m:
            m.return_value = {
                "id": "job-new",
                "company_id": TEST_COMPANY_ID,
                "title": "Dev Back",
                "status": "draft",
                "candidate_count": 0,
                "created_at": "",
                "updated_at": "",
            }
            response = recruitment_client.post(
                "/api/recruitment/jobs",
                json={"title": "Dev Back", "status": "draft"},
            )
        assert response.status_code == 200
        assert response.json()["title"] == "Dev Back"

    def test_update_job_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.update_job") as m:
            m.return_value = {
                "id": "job-1",
                "company_id": TEST_COMPANY_ID,
                "title": "Dev Back (modifié)",
                "status": "published",
                "candidate_count": 0,
                "created_at": "",
                "updated_at": "",
            }
            response = recruitment_client.patch(
                "/api/recruitment/jobs/job-1",
                json={"title": "Dev Back (modifié)", "status": "published"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "published"


# ─── Pipeline stages ──────────────────────────────────────────────────


class TestRecruitmentPipelineStages:
    """GET /api/recruitment/jobs/{job_id}/stages."""

    def test_get_stages_returns_200_and_list(self, recruitment_client: TestClient):
        with patch(
            "app.modules.recruitment.api.router.queries.get_pipeline_stages"
        ) as m:
            m.return_value = [
                {
                    "id": "s1",
                    "job_id": "job-1",
                    "name": "Premier appel",
                    "position": 0,
                    "stage_type": "standard",
                    "is_final": False,
                },
            ]
            response = recruitment_client.get("/api/recruitment/jobs/job-1/stages")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert response.json()[0]["name"] == "Premier appel"


# ─── Candidates ────────────────────────────────────────────────────────


class TestRecruitmentCandidates:
    """GET/POST/PATCH/DELETE /api/recruitment/candidates, move, check-duplicate, hire."""

    def test_list_candidates_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.list_candidates") as m:
            m.return_value = [
                {
                    "id": "c1",
                    "company_id": TEST_COMPANY_ID,
                    "job_id": "job-1",
                    "first_name": "Alice",
                    "last_name": "Martin",
                    "created_at": "",
                    "updated_at": "",
                },
            ]
            response = recruitment_client.get("/api/recruitment/candidates")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_create_candidate_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_candidate") as m:
            m.return_value = {
                "id": "cand-new",
                "company_id": TEST_COMPANY_ID,
                "job_id": "job-1",
                "first_name": "Alice",
                "last_name": "Martin",
                "created_at": "",
                "updated_at": "",
            }
            response = recruitment_client.post(
                "/api/recruitment/candidates",
                json={"job_id": "job-1", "first_name": "Alice", "last_name": "Martin"},
            )
        assert response.status_code == 200
        assert response.json()["first_name"] == "Alice"

    def test_get_candidate_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.get_candidate") as m:
            m.return_value = {
                "id": "cand-1",
                "company_id": TEST_COMPANY_ID,
                "job_id": "job-1",
                "first_name": "Alice",
                "last_name": "Martin",
                "created_at": "",
                "updated_at": "",
            }
            response = recruitment_client.get("/api/recruitment/candidates/cand-1")
        assert response.status_code == 200
        assert response.json()["id"] == "cand-1"

    def test_get_candidate_returns_404_when_not_found(
        self, recruitment_client: TestClient
    ):
        with patch("app.modules.recruitment.api.router.queries.get_candidate") as m:
            m.return_value = None
            response = recruitment_client.get(
                "/api/recruitment/candidates/cand-unknown"
            )
        assert response.status_code == 404

    def test_update_candidate_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.update_candidate") as m:
            m.return_value = {
                "id": "cand-1",
                "company_id": TEST_COMPANY_ID,
                "job_id": "job-1",
                "first_name": "Alice",
                "last_name": "Martin",
                "email": "alice@example.com",
                "created_at": "",
                "updated_at": "",
            }
            response = recruitment_client.patch(
                "/api/recruitment/candidates/cand-1",
                json={"email": "alice@example.com"},
            )
        assert response.status_code == 200

    def test_delete_candidate_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.delete_candidate"):
            response = recruitment_client.delete("/api/recruitment/candidates/cand-1")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_move_candidate_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.move_candidate") as m:
            m.return_value = {
                "id": "stage-5",
                "name": "Refusé",
                "stage_type": "rejected",
            }
            response = recruitment_client.post(
                "/api/recruitment/candidates/cand-1/move",
                json={"stage_id": "stage-5", "rejection_reason": "Profil non adapté"},
            )
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert "stage" in response.json()

    def test_check_duplicate_returns_200_with_warnings(
        self, recruitment_client: TestClient
    ):
        with patch("app.modules.recruitment.api.router.queries.check_duplicate") as m:
            m.return_value = {"warnings": []}
            response = recruitment_client.post(
                "/api/recruitment/candidates/cand-1/check-duplicate"
            )
        assert response.status_code == 200
        assert "warnings" in response.json()

    def test_hire_candidate_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.hire_candidate") as m:
            m.return_value = {"id": "emp-new"}
            response = recruitment_client.post(
                "/api/recruitment/candidates/cand-1/hire",
                json={"hire_date": "2025-03-01"},
            )
        assert response.status_code == 200
        assert response.json()["ok"] is True
        assert response.json()["employee_id"] == "emp-new"


# ─── Interviews ─────────────────────────────────────────────────────────


class TestRecruitmentInterviews:
    """GET/POST /api/recruitment/interviews, PATCH /api/recruitment/interviews/{id}."""

    def test_list_interviews_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.list_interviews") as m:
            m.return_value = []
            response = recruitment_client.get("/api/recruitment/interviews")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_interview_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_interview") as m:
            m.return_value = {
                "id": "int-new",
                "candidate_id": "cand-1",
                "interview_type": "Entretien RH",
                "scheduled_at": "2025-03-20T10:00:00",
                "duration_minutes": 60,
                "status": "scheduled",
                "created_at": "",
            }
            response = recruitment_client.post(
                "/api/recruitment/interviews",
                json={
                    "candidate_id": "cand-1",
                    "interview_type": "Entretien RH",
                    "scheduled_at": "2025-03-20T10:00:00",
                },
            )
        assert response.status_code == 200
        assert response.json()["interview_type"] == "Entretien RH"

    def test_update_interview_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.update_interview"):
            response = recruitment_client.patch(
                "/api/recruitment/interviews/int-1",
                json={"summary": "Très bien"},
            )
        assert response.status_code == 200
        assert response.json() == {"ok": True}


# ─── Notes & Opinions ───────────────────────────────────────────────────


class TestRecruitmentNotesAndOpinions:
    """GET/POST /api/recruitment/notes, GET/POST /api/recruitment/opinions."""

    def test_list_notes_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.list_notes") as m:
            m.return_value = []
            response = recruitment_client.get(
                "/api/recruitment/notes",
                params={"candidate_id": "cand-1"},
            )
        assert response.status_code == 200

    def test_create_note_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_note") as m:
            m.return_value = {
                "id": "note-1",
                "candidate_id": "cand-1",
                "content": "Bon contact.",
                "author_id": TEST_RH_USER_ID,
                "created_at": "",
            }
            response = recruitment_client.post(
                "/api/recruitment/notes",
                json={"candidate_id": "cand-1", "content": "Bon contact."},
            )
        assert response.status_code == 200
        assert response.json()["content"] == "Bon contact."

    def test_list_opinions_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.list_opinions") as m:
            m.return_value = []
            response = recruitment_client.get(
                "/api/recruitment/opinions",
                params={"candidate_id": "cand-1"},
            )
        assert response.status_code == 200

    def test_create_opinion_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_opinion") as m:
            m.return_value = {
                "id": "op-1",
                "candidate_id": "cand-1",
                "rating": "favorable",
                "author_id": TEST_RH_USER_ID,
                "created_at": "",
            }
            response = recruitment_client.post(
                "/api/recruitment/opinions",
                json={"candidate_id": "cand-1", "rating": "favorable"},
            )
        assert response.status_code == 200
        assert response.json()["rating"] == "favorable"


# ─── Timeline & Rejection reasons ───────────────────────────────────────


class TestRecruitmentTimelineAndRejectionReasons:
    """GET /api/recruitment/timeline, GET /api/recruitment/rejection-reasons."""

    def test_get_timeline_returns_200(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.get_timeline") as m:
            m.return_value = [
                {
                    "id": "e1",
                    "candidate_id": "cand-1",
                    "event_type": "candidate_created",
                    "description": "Créé",
                    "created_at": "",
                },
            ]
            response = recruitment_client.get(
                "/api/recruitment/timeline",
                params={"candidate_id": "cand-1"},
            )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_rejection_reasons_returns_200(self, recruitment_client: TestClient):
        with patch(
            "app.modules.recruitment.api.router.queries.get_rejection_reasons"
        ) as m:
            m.return_value = ["Profil non adapté", "Poste pourvu"]
            response = recruitment_client.get("/api/recruitment/rejection-reasons")
        assert response.status_code == 200
        assert "reasons" in response.json()
        assert "Profil non adapté" in response.json()["reasons"]
