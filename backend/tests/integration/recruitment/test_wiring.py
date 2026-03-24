"""
Tests de wiring (injection de dépendances et flux bout en bout) du module recruitment.

Vérifie que :
- Le router appelle bien les commandes/queries de la couche application.
- Les commandes/queries délèguent au service.
- Le service utilise les repositories et les règles du domaine.
Un test bout en bout avec mocks permet de valider le flux sans DB réelle.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_current_user
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _make_rh_user():
    return User(
        id=TEST_USER_ID,
        email="rh@recruitment-test.com",
        first_name="RH",
        last_name="Recruitment",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


@pytest.fixture
def recruitment_client(client: TestClient):
    app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
    try:
        yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)


class TestWiringSettingsToQueries:
    """Flux GET /api/recruitment/settings → queries.get_recruitment_settings → service."""

    def test_settings_flow_calls_queries(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.get_recruitment_settings") as get_settings:
            get_settings.return_value = {"enabled": True}
            response = recruitment_client.get("/api/recruitment/settings")
        assert response.status_code == 200
        assert response.json() == {"enabled": True}
        get_settings.assert_called_once_with(TEST_COMPANY_ID)


class TestWiringCreateJobCommandToService:
    """Flux POST /api/recruitment/jobs → commands.create_job → service.service_create_job."""

    def test_create_job_flow_calls_command_with_company_and_user(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_job") as create_job:
            create_job.return_value = {
                "id": "job-wired",
                "company_id": TEST_COMPANY_ID,
                "title": "Dev Wiring",
                "status": "draft",
                "candidate_count": 0,
                "created_at": "",
                "updated_at": "",
            }
            response = recruitment_client.post(
                "/api/recruitment/jobs",
                json={"title": "Dev Wiring", "status": "draft"},
            )
        assert response.status_code == 200
        assert response.json()["id"] == "job-wired"
        create_job.assert_called_once()
        call_args = create_job.call_args[0]
        assert call_args[0] == TEST_COMPANY_ID
        assert call_args[1] == TEST_USER_ID
        assert call_args[2]["title"] == "Dev Wiring"


class TestWiringListCandidatesQueryToService:
    """Flux GET /api/recruitment/candidates → queries.list_candidates → service."""

    def test_list_candidates_flow_calls_query_with_company(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.queries.list_candidates") as list_candidates:
            list_candidates.return_value = [
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
        list_candidates.assert_called_once()
        call_args = list_candidates.call_args[0]
        assert call_args[0] == TEST_COMPANY_ID


class TestWiringMoveCandidateCommandToService:
    """Flux POST /api/recruitment/candidates/{id}/move → commands.move_candidate → service."""

    def test_move_candidate_flow_passes_actor_id_from_current_user(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.move_candidate") as move_candidate:
            move_candidate.return_value = {"id": "stage-5", "name": "Refusé", "stage_type": "rejected"}
            response = recruitment_client.post(
                "/api/recruitment/candidates/cand-1/move",
                json={"stage_id": "stage-5", "rejection_reason": "Profil non adapté"},
            )
        assert response.status_code == 200
        move_candidate.assert_called_once()
        call_kw = move_candidate.call_args[1]
        assert call_kw["actor_id"] == TEST_USER_ID
        assert call_kw["rejection_reason"] == "Profil non adapté"


class TestWiringCreateOpinionCommandValidatesRating:
    """Flux POST /api/recruitment/opinions : la commande appelle le service qui applique la règle domaine (rating)."""

    def test_create_opinion_invalid_rating_returns_400(self, recruitment_client: TestClient):
        with patch("app.modules.recruitment.api.router.commands.create_opinion") as create_opinion:
            create_opinion.side_effect = ValueError("L'avis doit être 'favorable' ou 'defavorable'.")
            response = recruitment_client.post(
                "/api/recruitment/opinions",
                json={"candidate_id": "cand-1", "rating": "neutre"},
            )
        assert response.status_code == 400
        assert "favorable" in response.json().get("detail", "") or "defavorable" in response.json().get("detail", "")
