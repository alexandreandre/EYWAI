"""
Tests unitaires des commandes du module recruitment (application/commands.py).

Repositories et service mockés via patch du module service appelé par les commandes.
Pas de DB ni HTTP.
"""
from unittest.mock import patch

import pytest

from app.modules.recruitment.application import commands


@pytest.fixture(autouse=True)
def _patch_service():
    """Patch le module service utilisé par commands pour contrôler les retours."""
    with patch("app.modules.recruitment.application.commands.svc") as mock_svc:
        yield mock_svc


class TestCreateJob:
    """Commande create_job."""

    def test_returns_service_result(self, _patch_service):
        _patch_service.service_create_job.return_value = {
            "id": "job-new",
            "company_id": "co-1",
            "title": "Dev Back",
            "status": "draft",
            "candidate_count": 0,
        }
        result = commands.create_job("co-1", "user-1", {"title": "Dev Back"})
        assert result["id"] == "job-new"
        assert result["title"] == "Dev Back"
        _patch_service.service_create_job.assert_called_once_with(
            "co-1", "user-1", {"title": "Dev Back"}
        )

    def test_raises_value_error_from_service(self, _patch_service):
        _patch_service.service_create_job.side_effect = ValueError("Erreur création")
        with pytest.raises(ValueError, match="Erreur création"):
            commands.create_job("co-1", "user-1", {"title": "Dev"})


class TestUpdateJob:
    """Commande update_job."""

    def test_returns_updated_job(self, _patch_service):
        _patch_service.service_update_job.return_value = {
            "id": "job-1",
            "company_id": "co-1",
            "title": "Dev Back (modifié)",
            "status": "published",
        }
        result = commands.update_job(
            "job-1", "co-1", {"title": "Dev Back (modifié)", "status": "published"}
        )
        assert result["title"] == "Dev Back (modifié)"
        _patch_service.service_update_job.assert_called_once_with(
            "job-1", "co-1", {"title": "Dev Back (modifié)", "status": "published"}
        )

    def test_raises_value_error_poste_non_trouve(self, _patch_service):
        _patch_service.service_update_job.side_effect = ValueError("Poste non trouvé")
        with pytest.raises(ValueError, match="Poste non trouvé"):
            commands.update_job("job-unknown", "co-1", {"title": "X"})


class TestCreateCandidate:
    """Commande create_candidate."""

    def test_returns_created_candidate(self, _patch_service):
        _patch_service.service_create_candidate.return_value = {
            "id": "cand-new",
            "company_id": "co-1",
            "job_id": "job-1",
            "first_name": "Alice",
            "last_name": "Martin",
            "email": "alice@example.com",
        }
        data = {
            "job_id": "job-1",
            "first_name": "Alice",
            "last_name": "Martin",
            "email": "alice@example.com",
        }
        result = commands.create_candidate("co-1", "user-1", data)
        assert result["id"] == "cand-new"
        assert result["first_name"] == "Alice"
        _patch_service.service_create_candidate.assert_called_once_with(
            "co-1", "user-1", data
        )

    def test_raises_value_error_poste_non_trouve(self, _patch_service):
        _patch_service.service_create_candidate.side_effect = ValueError("Poste non trouvé")
        with pytest.raises(ValueError, match="Poste non trouvé"):
            commands.create_candidate("co-1", "user-1", {"job_id": "job-x", "first_name": "A", "last_name": "B"})


class TestUpdateCandidate:
    """Commande update_candidate."""

    def test_returns_updated_candidate(self, _patch_service):
        _patch_service.service_update_candidate.return_value = {
            "id": "cand-1",
            "first_name": "Alice",
            "last_name": "Martin",
            "email": "alice.new@example.com",
        }
        result = commands.update_candidate(
            "cand-1", "co-1", {"email": "alice.new@example.com"}
        )
        assert result["email"] == "alice.new@example.com"
        _patch_service.service_update_candidate.assert_called_once_with(
            "cand-1", "co-1", {"email": "alice.new@example.com"}
        )


class TestDeleteCandidate:
    """Commande delete_candidate."""

    def test_calls_service_and_returns_none(self, _patch_service):
        _patch_service.service_delete_candidate.return_value = None
        commands.delete_candidate("cand-1", "co-1")
        _patch_service.service_delete_candidate.assert_called_once_with(
            "cand-1", "co-1"
        )

    def test_raises_value_error_candidate_avance_pipeline(self, _patch_service):
        _patch_service.service_delete_candidate.side_effect = ValueError(
            "Impossible de supprimer un candidat avancé dans le pipeline. Utilisez le refus."
        )
        with pytest.raises(ValueError, match="avancé dans le pipeline"):
            commands.delete_candidate("cand-1", "co-1")


class TestMoveCandidate:
    """Commande move_candidate."""

    def test_returns_stage_data(self, _patch_service):
        _patch_service.service_move_candidate.return_value = {
            "id": "stage-5",
            "name": "Refusé",
            "stage_type": "rejected",
            "position": 5,
        }
        result = commands.move_candidate(
            "cand-1",
            "co-1",
            "stage-5",
            rejection_reason="Profil non adapté",
            rejection_reason_detail="Détail",
            actor_id="user-1",
        )
        assert result["name"] == "Refusé"
        _patch_service.service_move_candidate.assert_called_once_with(
            "cand-1",
            "co-1",
            "stage-5",
            rejection_reason="Profil non adapté",
            rejection_reason_detail="Détail",
            actor_id="user-1",
        )

    def test_raises_value_error_motif_refus_obligatoire(self, _patch_service):
        _patch_service.service_move_candidate.side_effect = ValueError(
            "Un motif de refus est obligatoire."
        )
        with pytest.raises(ValueError, match="motif de refus"):
            commands.move_candidate("cand-1", "co-1", "stage-rejected")


class TestCreateInterview:
    """Commande create_interview."""

    def test_returns_created_interview(self, _patch_service):
        _patch_service.service_create_interview.return_value = {
            "id": "int-new",
            "candidate_id": "cand-1",
            "interview_type": "Entretien RH",
            "scheduled_at": "2025-03-20T10:00:00",
            "duration_minutes": 60,
            "status": "scheduled",
        }
        data = {
            "candidate_id": "cand-1",
            "interview_type": "Entretien RH",
            "scheduled_at": "2025-03-20T10:00:00",
        }
        result = commands.create_interview("co-1", "user-1", data)
        assert result["id"] == "int-new"
        _patch_service.service_create_interview.assert_called_once_with(
            "co-1", "user-1", data
        )

    def test_raises_value_error_candidat_non_trouve(self, _patch_service):
        _patch_service.service_create_interview.side_effect = ValueError("Candidat non trouvé")
        with pytest.raises(ValueError, match="Candidat non trouvé"):
            commands.create_interview(
                "co-1", "user-1", {"candidate_id": "cand-x", "scheduled_at": "2025-03-20T10:00:00"}
            )


class TestUpdateInterview:
    """Commande update_interview."""

    def test_calls_service_returns_none(self, _patch_service):
        commands.update_interview(
            "int-1", "co-1", {"summary": "Très bien"}, is_rh=False
        )
        _patch_service.service_update_interview.assert_called_once_with(
            "int-1", "co-1", {"summary": "Très bien"}, False
        )


class TestCreateNote:
    """Commande create_note."""

    def test_returns_created_note(self, _patch_service):
        _patch_service.service_create_note.return_value = {
            "id": "note-new",
            "candidate_id": "cand-1",
            "content": "Bon contact.",
            "author_id": "user-1",
        }
        data = {"candidate_id": "cand-1", "content": "Bon contact."}
        result = commands.create_note("co-1", "user-1", data)
        assert result["id"] == "note-new"
        assert result["content"] == "Bon contact."
        _patch_service.service_create_note.assert_called_once_with(
            "co-1", "user-1", data
        )


class TestCreateOpinion:
    """Commande create_opinion."""

    def test_returns_created_opinion_favorable(self, _patch_service):
        _patch_service.service_create_opinion.return_value = {
            "id": "opinion-new",
            "candidate_id": "cand-1",
            "rating": "favorable",
            "author_id": "user-1",
        }
        data = {"candidate_id": "cand-1", "rating": "favorable"}
        result = commands.create_opinion("co-1", "user-1", data)
        assert result["rating"] == "favorable"
        _patch_service.service_create_opinion.assert_called_once_with(
            "co-1", "user-1", data
        )

    def test_raises_value_error_rating_invalide(self, _patch_service):
        _patch_service.service_create_opinion.side_effect = ValueError(
            "L'avis doit être 'favorable' ou 'defavorable'."
        )
        with pytest.raises(ValueError, match="favorable.*defavorable"):
            commands.create_opinion(
                "co-1", "user-1", {"candidate_id": "cand-1", "rating": "neutre"}
            )


class TestHireCandidate:
    """Commande hire_candidate."""

    def test_returns_employee_created(self, _patch_service):
        _patch_service.service_hire_candidate.return_value = {
            "id": "emp-new",
            "first_name": "Alice",
            "last_name": "Martin",
            "hire_date": "2025-03-01",
        }
        result = commands.hire_candidate(
            "cand-1",
            "co-1",
            "2025-03-01",
            site="Paris",
            service_name="Tech",
            job_title="Développeur",
            contract_type="CDI",
            actor_id="user-1",
        )
        assert result["id"] == "emp-new"
        _patch_service.service_hire_candidate.assert_called_once_with(
            "cand-1",
            "co-1",
            "2025-03-01",
            site="Paris",
            service_name="Tech",
            job_title="Développeur",
            contract_type="CDI",
            actor_id="user-1",
        )

    def test_raises_value_error_candidat_introuvable(self, _patch_service):
        _patch_service.service_hire_candidate.side_effect = ValueError("Candidat non trouvé")
        with pytest.raises(ValueError, match="Candidat non trouvé"):
            commands.hire_candidate("cand-unknown", "co-1", "2025-03-01")
