"""
Tests d'intégration du repository et des queries infrastructure du module recruitment.

JobRepository, CandidateRepository, PipelineStageRepository, TimelineEventWriter/Reader,
DuplicateChecker, InterviewRepository, NoteRepository, OpinionRepository :
tests avec mocks Supabase pour valider la logique et les appels.

Pour exécuter contre une DB de test réelle : ajouter dans conftest.py une fixture
db_session (connexion Supabase de test) et une fixture recruitment_db_session(db_session)
pour les tables recruitment_jobs, recruitment_candidates, recruitment_pipeline_stages,
recruitment_timeline_events, recruitment_interviews, recruitment_notes, recruitment_opinions,
recruitment_interview_participants, et employees (pour DuplicateChecker / EmployeeCreator).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.recruitment.infrastructure.repository import (
    JobRepository,
    CandidateRepository,
    PipelineStageRepository,
    TimelineEventWriter,
    DuplicateChecker,
    InterviewRepository,
    NoteRepository,
    OpinionRepository,
)
from app.modules.recruitment.infrastructure import queries as infra_queries


pytestmark = pytest.mark.integration


class TestJobRepository:
    """JobRepository : get_by_id, list_by_company, create, update."""

    def test_get_by_id_returns_none_when_not_found(self):
        with patch("app.modules.recruitment.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = JobRepository()
            result = repo.get_by_id("co-1", "job-unknown")

        assert result is None
        supabase.table.assert_called_with("recruitment_jobs")

    def test_get_by_id_returns_job_when_found(self):
        with patch("app.modules.recruitment.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            # maybe_single() peut retourner un seul objet (dict) selon le client Supabase
            chain.maybe_single.return_value.execute.return_value = MagicMock(
                data={"id": "job-1", "company_id": "co-1", "title": "Dev", "status": "draft"}
            )
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            with patch("app.modules.recruitment.infrastructure.repository.job_row_to_out") as mapper:
                mapper.return_value = {"id": "job-1", "title": "Dev", "candidate_count": 0}
                repo = JobRepository()
                result = repo.get_by_id("co-1", "job-1")

        assert result is not None
        assert result["id"] == "job-1"

    def test_list_by_company_delegates_to_infra_queries(self):
        with patch("app.modules.recruitment.infrastructure.repository.q") as q:
            q.list_jobs_with_candidate_count.return_value = [
                {"id": "job-1", "title": "Dev", "candidate_count": 2},
            ]
            repo = JobRepository()
            result = repo.list_by_company("co-1", status="published")
            assert len(result) == 1
            assert result[0]["title"] == "Dev"
            q.list_jobs_with_candidate_count.assert_called_once_with("co-1", "published")


class TestCandidateRepository:
    """CandidateRepository : get_by_id, list_by_company, create, update, delete."""

    def test_get_by_id_delegates_to_infra_queries(self):
        with patch("app.modules.recruitment.infrastructure.repository.q") as q:
            q.get_candidate.return_value = {
                "id": "cand-1",
                "first_name": "Alice",
                "last_name": "Martin",
                "job_id": "job-1",
            }
            repo = CandidateRepository()
            result = repo.get_by_id("co-1", "cand-1")
            assert result["id"] == "cand-1"
            q.get_candidate.assert_called_once_with("co-1", "cand-1")

    def test_create_inserts_and_returns_mapped(self):
        with patch("app.modules.recruitment.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            table_mock.insert.return_value.execute.return_value = MagicMock(
                data=[{"id": "cand-new", "first_name": "Alice", "last_name": "Martin", "company_id": "co-1", "job_id": "job-1"}]
            )
            supabase.table.return_value = table_mock
            with patch("app.modules.recruitment.infrastructure.repository.candidate_row_to_out") as mapper:
                mapper.return_value = {"id": "cand-new", "first_name": "Alice", "last_name": "Martin"}
                repo = CandidateRepository()
                result = repo.create("co-1", {"first_name": "Alice", "last_name": "Martin", "job_id": "job-1"})
            assert result["id"] == "cand-new"

    def test_delete_calls_supabase_delete(self):
        with patch("app.modules.recruitment.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            table_mock.delete.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            repo = CandidateRepository()
            repo.delete("cand-1", "co-1")

            supabase.table.assert_called_with("recruitment_candidates")
            table_mock.delete.return_value.eq.assert_called_once_with("id", "cand-1")


class TestPipelineStageRepository:
    """PipelineStageRepository : list_by_job, create_default_for_job."""

    def test_list_by_job_delegates_to_queries(self):
        with patch("app.modules.recruitment.infrastructure.repository.q") as q:
            q.get_pipeline_stages.return_value = [
                {"id": "s1", "name": "Premier appel", "position": 0, "stage_type": "standard", "is_final": False},
            ]
            repo = PipelineStageRepository()
            result = repo.list_by_job("co-1", "job-1")
            assert len(result) == 1
            q.get_pipeline_stages.assert_called_once_with("co-1", "job-1")


class TestTimelineEventWriter:
    """TimelineEventWriter : add."""

    def test_add_inserts_event(self):
        with patch("app.modules.recruitment.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            table_mock.insert.return_value.execute.return_value = MagicMock()
            supabase.table.return_value = table_mock

            writer = TimelineEventWriter()
            writer.add(
                company_id="co-1",
                candidate_id="cand-1",
                event_type="stage_changed",
                description="Déplacé vers Entretien RH",
                actor_id="user-1",
            )

            supabase.table.assert_called_with("recruitment_timeline_events")
            call_args = table_mock.insert.call_args[0][0]
            assert call_args["event_type"] == "stage_changed"
            assert call_args["candidate_id"] == "cand-1"


class TestDuplicateChecker:
    """DuplicateChecker : check_duplicate_candidate, check_duplicate_employee."""

    def test_check_duplicate_candidate_returns_none_when_no_email_phone(self):
        checker = DuplicateChecker()
        assert checker.check_duplicate_candidate("co-1", None, None) is None

    def test_check_duplicate_candidate_returns_match_when_email_exists(self):
        with patch("app.modules.recruitment.infrastructure.repository.supabase") as supabase:
            table_mock = MagicMock()
            chain = MagicMock()
            chain.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "cand-2", "first_name": "Bob", "last_name": "Dupont", "email": "bob@example.com"}]
            )
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            checker = DuplicateChecker()
            result = checker.check_duplicate_candidate("co-1", "bob@example.com", None)
            assert result is not None
            assert result["id"] == "cand-2"

    def test_check_duplicate_employee_returns_none_when_no_email(self):
        checker = DuplicateChecker()
        assert checker.check_duplicate_employee("co-1", None, None) is None


class TestInterviewRepository:
    """InterviewRepository : list_by_company, create, update."""

    def test_list_by_company_delegates_to_queries(self):
        with patch("app.modules.recruitment.infrastructure.repository.q") as q:
            q.list_interviews.return_value = []
            repo = InterviewRepository()
            result = repo.list_by_company("co-1", candidate_id="cand-1")
            assert result == []
            q.list_interviews.assert_called_once_with(
                "co-1", candidate_id="cand-1", participant_user_id=None
            )


class TestNoteRepository:
    """NoteRepository : list_by_candidate, create."""

    def test_list_by_candidate_delegates_to_queries(self):
        with patch("app.modules.recruitment.infrastructure.repository.q") as q:
            q.list_notes.return_value = [{"id": "n1", "content": "OK", "candidate_id": "cand-1", "author_id": "u1", "created_at": ""}]
            repo = NoteRepository()
            result = repo.list_by_candidate("co-1", "cand-1")
            assert len(result) == 1
            q.list_notes.assert_called_once_with("co-1", "cand-1")


class TestOpinionRepository:
    """OpinionRepository : list_by_candidate, create."""

    def test_list_by_candidate_delegates_to_queries(self):
        with patch("app.modules.recruitment.infrastructure.repository.q") as q:
            q.list_opinions.return_value = []
            repo = OpinionRepository()
            result = repo.list_by_candidate("co-1", "cand-1")
            assert result == []
            q.list_opinions.assert_called_once_with("co-1", "cand-1")


# ─── Infrastructure queries (lectures directes) ────────────────────────

class TestInfraQueries:
    """Fonctions du module infrastructure/queries.py avec supabase mocké."""

    def test_get_candidate_returns_none_when_not_found(self):
        with patch("app.modules.recruitment.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            table_mock = MagicMock()
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_candidate("co-1", "cand-unknown")
        assert result is None

    def test_get_candidate_with_stage_position_returns_none_when_not_found(self):
        with patch("app.modules.recruitment.infrastructure.queries.supabase") as supabase:
            chain = MagicMock()
            chain.maybe_single.return_value.execute.return_value = MagicMock(data=None)
            table_mock = MagicMock()
            table_mock.select.return_value.eq.return_value.eq.return_value = chain
            supabase.table.return_value = table_mock

            result = infra_queries.get_candidate_with_stage_position("co-1", "cand-unknown")
        assert result is None
