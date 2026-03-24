"""
Tests unitaires des requêtes du module recruitment (application/queries.py).

Service et infrastructure mockés via patch du module service appelé par les queries.
Pas de DB ni HTTP.
"""
from unittest.mock import patch

import pytest

from app.modules.recruitment.application import queries


@pytest.fixture(autouse=True)
def _patch_service():
    """Patch le module service utilisé par queries."""
    with patch("app.modules.recruitment.application.queries.svc") as mock_svc:
        yield mock_svc


class TestGetRecruitmentSettings:
    """Query get_recruitment_settings."""

    def test_returns_enabled_true(self, _patch_service):
        _patch_service.get_recruitment_setting.return_value = True
        result = queries.get_recruitment_settings("co-1")
        assert result == {"enabled": True}
        _patch_service.get_recruitment_setting.assert_called_once_with("co-1")

    def test_returns_enabled_false(self, _patch_service):
        _patch_service.get_recruitment_setting.return_value = False
        result = queries.get_recruitment_settings("co-2")
        assert result == {"enabled": False}


class TestListJobs:
    """Query list_jobs."""

    def test_returns_list_from_service(self, _patch_service):
        _patch_service.service_list_jobs.return_value = [
            {"id": "job-1", "title": "Dev Back", "candidate_count": 2},
            {"id": "job-2", "title": "Data", "candidate_count": 0},
        ]
        result = queries.list_jobs("co-1")
        assert len(result) == 2
        assert result[0]["title"] == "Dev Back"
        _patch_service.service_list_jobs.assert_called_once_with("co-1", None)

    def test_passes_status_filter(self, _patch_service):
        _patch_service.service_list_jobs.return_value = []
        queries.list_jobs("co-1", status="published")
        _patch_service.service_list_jobs.assert_called_once_with("co-1", "published")


class TestGetPipelineStages:
    """Query get_pipeline_stages."""

    def test_returns_stages_from_service(self, _patch_service):
        _patch_service.service_get_pipeline_stages.return_value = [
            {"id": "s1", "name": "Premier appel", "position": 0, "stage_type": "standard"},
            {"id": "s2", "name": "Entretien RH", "position": 1, "stage_type": "standard"},
        ]
        result = queries.get_pipeline_stages("co-1", "job-1")
        assert len(result) == 2
        assert result[0]["name"] == "Premier appel"
        _patch_service.service_get_pipeline_stages.assert_called_once_with("co-1", "job-1")


class TestListCandidates:
    """Query list_candidates."""

    def test_returns_list_with_filters(self, _patch_service):
        _patch_service.service_list_candidates.return_value = [
            {"id": "c1", "first_name": "Alice", "last_name": "Martin", "job_id": "job-1"},
        ]
        result = queries.list_candidates(
            "co-1",
            job_id="job-1",
            stage_id="stage-1",
            search="alice",
            participant_user_id="user-1",
        )
        assert len(result) == 1
        assert result[0]["first_name"] == "Alice"
        _patch_service.service_list_candidates.assert_called_once_with(
            "co-1",
            job_id="job-1",
            stage_id="stage-1",
            search="alice",
            participant_user_id="user-1",
        )


class TestGetCandidate:
    """Query get_candidate."""

    def test_returns_candidate_when_found(self, _patch_service):
        _patch_service.service_get_candidate.return_value = {
            "id": "cand-1",
            "first_name": "Alice",
            "last_name": "Martin",
            "job_id": "job-1",
        }
        result = queries.get_candidate("co-1", "cand-1")
        assert result is not None
        assert result["id"] == "cand-1"
        _patch_service.service_get_candidate.assert_called_once_with("co-1", "cand-1")

    def test_returns_none_when_not_found(self, _patch_service):
        _patch_service.service_get_candidate.return_value = None
        result = queries.get_candidate("co-1", "cand-unknown")
        assert result is None


class TestListInterviews:
    """Query list_interviews."""

    def test_returns_list_from_service(self, _patch_service):
        _patch_service.service_list_interviews.return_value = [
            {"id": "int-1", "candidate_id": "cand-1", "scheduled_at": "2025-03-20T10:00:00"},
        ]
        result = queries.list_interviews(
            "co-1",
            candidate_id="cand-1",
            participant_user_id="user-1",
        )
        assert len(result) == 1
        _patch_service.service_list_interviews.assert_called_once_with(
            "co-1",
            candidate_id="cand-1",
            participant_user_id="user-1",
        )


class TestListNotes:
    """Query list_notes."""

    def test_returns_notes_for_candidate(self, _patch_service):
        _patch_service.service_list_notes.return_value = [
            {"id": "n1", "candidate_id": "cand-1", "content": "Bon contact."},
        ]
        result = queries.list_notes("co-1", "cand-1")
        assert len(result) == 1
        assert result[0]["content"] == "Bon contact."
        _patch_service.service_list_notes.assert_called_once_with("co-1", "cand-1")


class TestListOpinions:
    """Query list_opinions."""

    def test_returns_opinions_for_candidate(self, _patch_service):
        _patch_service.service_list_opinions.return_value = [
            {"id": "o1", "candidate_id": "cand-1", "rating": "favorable"},
        ]
        result = queries.list_opinions("co-1", "cand-1")
        assert len(result) == 1
        assert result[0]["rating"] == "favorable"
        _patch_service.service_list_opinions.assert_called_once_with("co-1", "cand-1")


class TestGetTimeline:
    """Query get_timeline."""

    def test_returns_timeline_events(self, _patch_service):
        _patch_service.service_get_timeline.return_value = [
            {"id": "e1", "event_type": "candidate_created", "description": "Candidat créé"},
        ]
        result = queries.get_timeline("co-1", "cand-1")
        assert len(result) == 1
        assert result[0]["event_type"] == "candidate_created"
        _patch_service.service_get_timeline.assert_called_once_with("co-1", "cand-1")


class TestGetRejectionReasons:
    """Query get_rejection_reasons."""

    def test_returns_list_from_service(self, _patch_service):
        _patch_service.get_rejection_reasons_list.return_value = [
            "Profil non adapté",
            "Manque d'expérience",
            "Poste pourvu",
        ]
        result = queries.get_rejection_reasons()
        assert len(result) == 3
        assert "Profil non adapté" in result
        _patch_service.get_rejection_reasons_list.assert_called_once()


class TestCheckDuplicate:
    """Query check_duplicate."""

    def test_returns_warnings_dict(self, _patch_service):
        _patch_service.service_check_duplicate_warnings.return_value = [
            {"type": "candidate", "existing_id": "cand-2", "first_name": "Bob", "last_name": "Dupont", "email": "bob@example.com"},
        ]
        result = queries.check_duplicate("co-1", "cand-1")
        assert "warnings" in result
        assert len(result["warnings"]) == 1
        assert result["warnings"][0]["type"] == "candidate"
        _patch_service.service_check_duplicate_warnings.assert_called_once_with(
            "co-1", "cand-1"
        )

    def test_raises_value_error_candidate_not_found(self, _patch_service):
        _patch_service.service_check_duplicate_warnings.side_effect = ValueError(
            "Candidat non trouvé"
        )
        with pytest.raises(ValueError, match="Candidat non trouvé"):
            queries.check_duplicate("co-1", "cand-unknown")


class TestIsUserParticipantForCandidate:
    """Query is_user_participant_for_candidate."""

    def test_returns_true_when_participant(self, _patch_service):
        _patch_service.is_user_participant_for_candidate.return_value = True
        result = queries.is_user_participant_for_candidate("user-1", "cand-1")
        assert result is True
        _patch_service.is_user_participant_for_candidate.assert_called_once_with(
            "user-1", "cand-1"
        )

    def test_returns_false_when_not_participant(self, _patch_service):
        _patch_service.is_user_participant_for_candidate.return_value = False
        result = queries.is_user_participant_for_candidate("user-2", "cand-1")
        assert result is False
