"""
Tests unitaires du service applicatif recruitment (application/service.py).

Dépendances (repositories, providers, infra queries) mockées. Pas de DB ni HTTP.
Vérifie l'orchestration : règles domaine + appels infrastructure.
"""
from unittest.mock import patch

import pytest

from app.modules.recruitment.application import service as svc


@pytest.fixture
def mock_repos():
    """Mocks pour les repositories et readers injectés dans le service."""
    with patch("app.modules.recruitment.application.service._settings_reader") as settings:
        with patch("app.modules.recruitment.application.service._job_repo") as job_repo:
            with patch("app.modules.recruitment.application.service._pipeline_stage_repo") as stage_repo:
                with patch("app.modules.recruitment.application.service._candidate_repo") as cand_repo:
                    with patch("app.modules.recruitment.application.service._timeline_writer") as timeline:
                        with patch("app.modules.recruitment.application.service._timeline_reader") as timeline_reader:
                            with patch("app.modules.recruitment.application.service._interview_repo") as interview_repo:
                                with patch("app.modules.recruitment.application.service._note_repo") as note_repo:
                                    with patch("app.modules.recruitment.application.service._opinion_repo") as opinion_repo:
                                        with patch("app.modules.recruitment.application.service._duplicate_checker") as dup:
                                            with patch("app.modules.recruitment.application.service._employee_creator") as emp_creator:
                                                with patch("app.modules.recruitment.application.service._participant_checker") as participant:
                                                    with patch("app.modules.recruitment.application.service.infra_queries") as infra_q:
                                                        yield {
                                                            "settings": settings,
                                                            "job_repo": job_repo,
                                                            "stage_repo": stage_repo,
                                                            "cand_repo": cand_repo,
                                                            "timeline": timeline,
                                                            "timeline_reader": timeline_reader,
                                                            "interview_repo": interview_repo,
                                                            "note_repo": note_repo,
                                                            "opinion_repo": opinion_repo,
                                                            "duplicate_checker": dup,
                                                            "employee_creator": emp_creator,
                                                            "participant_checker": participant,
                                                            "infra_queries": infra_q,
                                                        }


class TestGetRecruitmentSetting:
    """get_recruitment_setting."""

    def test_delegates_to_settings_reader(self, mock_repos):
        mock_repos["settings"].is_enabled.return_value = True
        assert svc.get_recruitment_setting("co-1") is True
        mock_repos["settings"].is_enabled.assert_called_once_with("co-1")


class TestServiceCreateJob:
    """service_create_job."""

    def test_creates_job_and_default_pipeline(self, mock_repos):
        mock_repos["job_repo"].create.return_value = {
            "id": "job-new",
            "company_id": "co-1",
            "title": "Dev",
            "status": "draft",
        }
        mock_repos["stage_repo"].create_default_for_job.return_value = []
        result = svc.service_create_job(
            "co-1", "user-1", {"title": "Dev", "description": "Backend"}
        )
        assert result["id"] == "job-new"
        mock_repos["job_repo"].create.assert_called_once()
        call_args = mock_repos["job_repo"].create.call_args[0]
        assert call_args[0] == "co-1"
        call_kw = call_args[1]
        assert call_kw["title"] == "Dev"
        assert call_kw.get("status") == "draft"
        mock_repos["stage_repo"].create_default_for_job.assert_called_once_with(
            "co-1", "job-new"
        )


class TestServiceUpdateJob:
    """service_update_job."""

    def test_raises_when_job_not_found(self, mock_repos):
        mock_repos["job_repo"].get_by_id.return_value = None
        with pytest.raises(ValueError, match="Poste non trouvé"):
            svc.service_update_job("job-1", "co-1", {"title": "X"})

    def test_raises_when_no_updates(self, mock_repos):
        mock_repos["job_repo"].get_by_id.return_value = {"id": "job-1"}
        with pytest.raises(ValueError, match="Aucune modification"):
            svc.service_update_job("job-1", "co-1", {})

    def test_updates_and_returns(self, mock_repos):
        mock_repos["job_repo"].get_by_id.return_value = {"id": "job-1"}
        mock_repos["job_repo"].update.return_value = {"id": "job-1", "title": "Dev Back"}
        result = svc.service_update_job("job-1", "co-1", {"title": "Dev Back"})
        assert result["title"] == "Dev Back"
        mock_repos["job_repo"].update.assert_called_once_with(
            "job-1", "co-1", {"title": "Dev Back"}
        )


class TestServiceCreateCandidate:
    """service_create_candidate."""

    def test_raises_when_job_not_found(self, mock_repos):
        mock_repos["job_repo"].get_by_id.return_value = None
        with pytest.raises(ValueError, match="Poste non trouvé"):
            svc.service_create_candidate(
                "co-1", "user-1", {"job_id": "job-x", "first_name": "A", "last_name": "B"}
            )

    def test_creates_candidate_and_timeline_event(self, mock_repos):
        mock_repos["job_repo"].get_by_id.return_value = {"id": "job-1"}
        mock_repos["stage_repo"].list_by_job.return_value = [{"id": "stage-0", "position": 0}]
        mock_repos["cand_repo"].create.return_value = {
            "id": "cand-new",
            "first_name": "Alice",
            "last_name": "Martin",
        }
        result = svc.service_create_candidate(
            "co-1",
            "user-1",
            {"job_id": "job-1", "first_name": "Alice", "last_name": "Martin"},
        )
        assert result["id"] == "cand-new"
        mock_repos["timeline"].add.assert_called_once()
        call_kw = mock_repos["timeline"].add.call_args[1]
        assert call_kw["event_type"] == "candidate_created"
        assert "Alice" in call_kw["description"]


class TestServiceDeleteCandidate:
    """service_delete_candidate."""

    def test_raises_when_candidate_not_found(self, mock_repos):
        mock_repos["infra_queries"].get_candidate_with_stage_position.return_value = None
        with pytest.raises(ValueError, match="Candidat non trouvé"):
            svc.service_delete_candidate("cand-x", "co-1")

    def test_raises_when_stage_position_above_1(self, mock_repos):
        mock_repos["infra_queries"].get_candidate_with_stage_position.return_value = {
            "id": "cand-1",
            "stage": {"position": 3},
        }
        with pytest.raises(ValueError, match="avancé dans le pipeline"):
            svc.service_delete_candidate("cand-1", "co-1")

    def test_deletes_when_position_1(self, mock_repos):
        mock_repos["infra_queries"].get_candidate_with_stage_position.return_value = {
            "id": "cand-1",
            "stage": {"position": 1},
        }
        svc.service_delete_candidate("cand-1", "co-1")
        mock_repos["cand_repo"].delete.assert_called_once_with("cand-1", "co-1")


class TestServiceMoveCandidate:
    """service_move_candidate."""

    def test_raises_when_candidate_not_found(self, mock_repos):
        mock_repos["cand_repo"].get_by_id.return_value = None
        with pytest.raises(ValueError, match="Candidat non trouvé"):
            svc.service_move_candidate("cand-x", "co-1", "stage-1")

    def test_raises_when_stage_not_found(self, mock_repos):
        mock_repos["cand_repo"].get_by_id.return_value = {"id": "cand-1", "job_id": "job-1"}
        mock_repos["stage_repo"].list_by_job.return_value = []
        with pytest.raises(ValueError, match="Étape non trouvée"):
            svc.service_move_candidate("cand-1", "co-1", "stage-unknown")

    def test_raises_when_rejected_without_reason(self, mock_repos):
        mock_repos["cand_repo"].get_by_id.return_value = {"id": "cand-1", "job_id": "job-1", "first_name": "A", "last_name": "B"}
        mock_repos["stage_repo"].list_by_job.return_value = [
            {"id": "stage-rej", "name": "Refusé", "stage_type": "rejected"},
        ]
        with pytest.raises(ValueError, match="motif de refus"):
            svc.service_move_candidate("cand-1", "co-1", "stage-rej", rejection_reason=None)

    def test_updates_and_writes_timeline_for_rejected(self, mock_repos):
        mock_repos["cand_repo"].get_by_id.return_value = {"id": "cand-1", "job_id": "job-1", "first_name": "Alice", "last_name": "Martin"}
        mock_repos["stage_repo"].list_by_job.return_value = [
            {"id": "stage-rej", "name": "Refusé", "stage_type": "rejected"},
        ]
        result = svc.service_move_candidate(
            "cand-1", "co-1", "stage-rej",
            rejection_reason="Profil non adapté",
            rejection_reason_detail="Détail",
            actor_id="user-1",
        )
        assert result["name"] == "Refusé"
        mock_repos["cand_repo"].update.assert_called_once()
        call_kw = mock_repos["cand_repo"].update.call_args[0][2]
        assert call_kw["rejection_reason"] == "Profil non adapté"
        mock_repos["timeline"].add.assert_called_once()
        assert mock_repos["timeline"].add.call_args[1]["event_type"] == "rejected"


class TestServiceCreateOpinion:
    """service_create_opinion."""

    def test_raises_when_rating_invalid(self, mock_repos):
        with pytest.raises(ValueError, match="favorable.*defavorable"):
            svc.service_create_opinion(
                "co-1", "user-1", {"candidate_id": "cand-1", "rating": "neutre"}
            )
        mock_repos["opinion_repo"].create.assert_not_called()

    def test_creates_opinion_and_timeline_when_favorable(self, mock_repos):
        mock_repos["opinion_repo"].create.return_value = {
            "id": "op-1", "candidate_id": "cand-1", "rating": "favorable",
        }
        result = svc.service_create_opinion(
            "co-1", "user-1", {"candidate_id": "cand-1", "rating": "favorable"}
        )
        assert result["rating"] == "favorable"
        mock_repos["timeline"].add.assert_called_once()
        desc = mock_repos["timeline"].add.call_args[1]["description"]
        assert "favorable" in desc.lower()


class TestServiceCheckDuplicateWarnings:
    """service_check_duplicate_warnings."""

    def test_raises_when_candidate_not_found(self, mock_repos):
        mock_repos["infra_queries"].get_candidate_email_phone.return_value = None
        with pytest.raises(ValueError, match="Candidat non trouvé"):
            svc.service_check_duplicate_warnings("co-1", "cand-x")

    def test_returns_candidate_warning_when_duplicate_candidate(self, mock_repos):
        mock_repos["infra_queries"].get_candidate_email_phone.return_value = {
            "email": "alice@example.com",
            "phone": None,
        }
        mock_repos["duplicate_checker"].check_duplicate_candidate.return_value = {
            "id": "cand-2",
            "first_name": "Alice",
            "last_name": "Other",
            "email": "alice@example.com",
        }
        mock_repos["duplicate_checker"].check_duplicate_employee.return_value = None
        result = svc.service_check_duplicate_warnings("co-1", "cand-1")
        assert len(result) == 1
        assert result[0]["type"] == "candidate"
        assert result[0]["existing_id"] == "cand-2"

    def test_returns_employee_warning_when_duplicate_employee(self, mock_repos):
        mock_repos["infra_queries"].get_candidate_email_phone.return_value = {
            "email": "alice@example.com",
            "phone": None,
        }
        mock_repos["duplicate_checker"].check_duplicate_candidate.return_value = None
        mock_repos["duplicate_checker"].check_duplicate_employee.return_value = {
            "id": "emp-1",
            "first_name": "Alice",
            "last_name": "Martin",
            "email": "alice@example.com",
        }
        result = svc.service_check_duplicate_warnings("co-1", "cand-1")
        assert len(result) == 1
        assert result[0]["type"] == "employee"


class TestGetRejectionReasonsList:
    """get_rejection_reasons_list (délégation provider)."""

    def test_returns_list_from_provider(self):
        result = svc.get_rejection_reasons_list()
        assert isinstance(result, list)
        assert "Profil non adapté" in result
        assert "Poste pourvu" in result


class TestIsUserParticipantForCandidate:
    """is_user_participant_for_candidate."""

    def test_delegates_to_participant_checker(self, mock_repos):
        mock_repos["participant_checker"].is_participant.return_value = True
        assert svc.is_user_participant_for_candidate("user-1", "cand-1") is True
        mock_repos["participant_checker"].is_participant.assert_called_once_with(
            "user-1", "cand-1"
        )
