"""
Tests unitaires du domaine recruitment : entités, value objects, règles, enums.

Sans DB, sans HTTP. Couvre domain/entities.py, domain/value_objects.py,
domain/rules.py, domain/enums.py.
"""
import pytest

from app.modules.recruitment.domain.entities import Job, Candidate, PipelineStage, Interview
from app.modules.recruitment.domain.rules import (
    VALID_OPINION_RATINGS,
    require_rejection_reason_for_rejected_stage,
    can_delete_candidate,
    is_valid_opinion_rating,
)
from app.modules.recruitment.domain.enums import StageType, OpinionRating


# ─── Entités ───────────────────────────────────────────────────────────

class TestJobEntity:
    """Entité Job : offre / poste à pourvoir."""

    def test_job_creation_with_required_fields(self):
        job = Job(
            id="job-1",
            company_id="co-1",
            title="Développeur Python",
            status="draft",
        )
        assert job.id == "job-1"
        assert job.company_id == "co-1"
        assert job.title == "Développeur Python"
        assert job.status == "draft"
        assert job.description is None
        assert job.created_at == ""

    def test_job_creation_with_optional_fields(self):
        job = Job(
            id="job-2",
            company_id="co-1",
            title="Data Analyst",
            status="published",
            description="Analyse de données",
            location="Paris",
            contract_type="CDI",
            tags=["data", "python"],
            created_by="user-1",
            created_at="2025-01-01T00:00:00",
            updated_at="2025-01-02T00:00:00",
        )
        assert job.description == "Analyse de données"
        assert job.location == "Paris"
        assert job.contract_type == "CDI"
        assert job.tags == ["data", "python"]
        assert job.created_by == "user-1"
        assert job.updated_at == "2025-01-02T00:00:00"


class TestCandidateEntity:
    """Entité Candidate : candidat à un poste."""

    def test_candidate_creation_required_fields(self):
        c = Candidate(
            id="cand-1",
            company_id="co-1",
            job_id="job-1",
            first_name="Jean",
            last_name="Dupont",
        )
        assert c.id == "cand-1"
        assert c.company_id == "co-1"
        assert c.job_id == "job-1"
        assert c.first_name == "Jean"
        assert c.last_name == "Dupont"
        assert c.current_stage_id is None
        assert c.email is None
        assert c.rejection_reason is None
        assert c.hired_at is None
        assert c.employee_id is None

    def test_candidate_creation_with_optional_fields(self):
        c = Candidate(
            id="cand-2",
            company_id="co-1",
            job_id="job-1",
            first_name="Marie",
            last_name="Martin",
            current_stage_id="stage-1",
            email="marie@example.com",
            phone="+33600000000",
            source="LinkedIn",
            rejection_reason="Profil non adapté",
            rejection_reason_detail="Manque d'expérience",
            hired_at="2025-02-01T00:00:00",
            employee_id="emp-1",
            created_at="2025-01-10T00:00:00",
            updated_at="2025-01-15T00:00:00",
        )
        assert c.email == "marie@example.com"
        assert c.phone == "+33600000000"
        assert c.source == "LinkedIn"
        assert c.rejection_reason == "Profil non adapté"
        assert c.employee_id == "emp-1"


class TestPipelineStageEntity:
    """Entité PipelineStage : étape du pipeline."""

    def test_pipeline_stage_creation(self):
        stage = PipelineStage(
            id="stage-1",
            job_id="job-1",
            company_id="co-1",
            name="Premier appel",
            position=0,
            stage_type="standard",
            is_final=False,
        )
        assert stage.id == "stage-1"
        assert stage.job_id == "job-1"
        assert stage.name == "Premier appel"
        assert stage.position == 0
        assert stage.stage_type == "standard"
        assert stage.is_final is False

    def test_pipeline_stage_final_rejected(self):
        stage = PipelineStage(
            id="stage-refused",
            job_id="job-1",
            company_id="co-1",
            name="Refusé",
            position=5,
            stage_type="rejected",
            is_final=True,
        )
        assert stage.stage_type == "rejected"
        assert stage.is_final is True


class TestInterviewEntity:
    """Entité Interview : entretien planifié."""

    def test_interview_creation_required_fields(self):
        i = Interview(
            id="int-1",
            company_id="co-1",
            candidate_id="cand-1",
            interview_type="Entretien RH",
            scheduled_at="2025-02-15T10:00:00",
            duration_minutes=60,
            status="scheduled",
        )
        assert i.id == "int-1"
        assert i.candidate_id == "cand-1"
        assert i.interview_type == "Entretien RH"
        assert i.scheduled_at == "2025-02-15T10:00:00"
        assert i.duration_minutes == 60
        assert i.status == "scheduled"
        assert i.location is None
        assert i.summary is None

    def test_interview_creation_with_optional_fields(self):
        i = Interview(
            id="int-2",
            company_id="co-1",
            candidate_id="cand-1",
            interview_type="Entretien technique",
            scheduled_at="2025-02-20T14:00:00",
            duration_minutes=90,
            status="done",
            location="Salle A",
            meeting_link="https://meet.example.com/abc",
            summary="Très bon entretien",
            created_by="user-1",
            created_at="2025-02-10T00:00:00",
        )
        assert i.location == "Salle A"
        assert i.meeting_link == "https://meet.example.com/abc"
        assert i.summary == "Très bon entretien"
        assert i.created_by == "user-1"


# ─── Règles métier ─────────────────────────────────────────────────────

class TestRequireRejectionReasonForRejectedStage:
    """Règle : étape rejected exige un motif de refus."""

    def test_standard_stage_always_ok(self):
        assert require_rejection_reason_for_rejected_stage("standard", None) is True
        assert require_rejection_reason_for_rejected_stage("standard", "") is True
        assert require_rejection_reason_for_rejected_stage("standard", "Profil non adapté") is True

    def test_hired_stage_always_ok(self):
        assert require_rejection_reason_for_rejected_stage("hired", None) is True

    def test_rejected_stage_requires_reason(self):
        assert require_rejection_reason_for_rejected_stage("rejected", None) is False
        assert require_rejection_reason_for_rejected_stage("rejected", "") is False
        assert require_rejection_reason_for_rejected_stage("rejected", "   ") is False
        assert require_rejection_reason_for_rejected_stage("rejected", "Profil non adapté") is True
        assert require_rejection_reason_for_rejected_stage("rejected", "Poste pourvu") is True


class TestCanDeleteCandidate:
    """Règle : suppression candidat autorisée seulement en début de pipeline (position <= 1)."""

    def test_position_0_or_1_can_delete(self):
        assert can_delete_candidate(0) is True
        assert can_delete_candidate(1) is True

    def test_position_above_1_cannot_delete(self):
        assert can_delete_candidate(2) is False
        assert can_delete_candidate(5) is False
        assert can_delete_candidate(10) is False


class TestIsValidOpinionRating:
    """Règle : avis doit être 'favorable' ou 'defavorable'."""

    def test_valid_ratings(self):
        assert is_valid_opinion_rating("favorable") is True
        assert is_valid_opinion_rating("defavorable") is True

    def test_invalid_ratings(self):
        assert is_valid_opinion_rating("") is False
        assert is_valid_opinion_rating("neutre") is False
        assert is_valid_opinion_rating("FAVORABLE") is False
        assert is_valid_opinion_rating("Favorable") is False


class TestValidOpinionRatingsConstant:
    """Constante VALID_OPINION_RATINGS."""

    def test_tuple_contains_favorable_and_defavorable(self):
        assert "favorable" in VALID_OPINION_RATINGS
        assert "defavorable" in VALID_OPINION_RATINGS
        assert len(VALID_OPINION_RATINGS) == 2


# ─── Enums ─────────────────────────────────────────────────────────────

class TestStageTypeEnum:
    """Enum StageType."""

    def test_values(self):
        assert StageType.STANDARD == "standard"
        assert StageType.REJECTED == "rejected"
        assert StageType.HIRED == "hired"

    def test_string_behavior(self):
        assert str(StageType.REJECTED) == "rejected"
        assert StageType.HIRED == "hired"


class TestOpinionRatingEnum:
    """Enum OpinionRating."""

    def test_values(self):
        assert OpinionRating.FAVORABLE == "favorable"
        assert OpinionRating.DEFAVORABLE == "defavorable"

    def test_matches_rules(self):
        assert OpinionRating.FAVORABLE in VALID_OPINION_RATINGS
        assert OpinionRating.DEFAVORABLE in VALID_OPINION_RATINGS
