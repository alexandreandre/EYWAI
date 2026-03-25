# app/modules/recruitment/infrastructure/repository.py
"""
Implémentations des interfaces domain (IJobRepository, etc.) avec Supabase.
Comportement identique au legacy. Accès DB via app.core.database.supabase.
"""

import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.database import supabase

from app.modules.recruitment.domain.interfaces import (
    ICandidateRepository,
    IDuplicateChecker,
    IEmployeeCreator,
    IJobRepository,
    IInterviewRepository,
    INoteRepository,
    IOpinionRepository,
    IPipelineStageRepository,
    IParticipantChecker,
    IRecruitmentSettingsReader,
    ITimelineEventReader,
    ITimelineEventWriter,
)
from app.modules.recruitment.infrastructure.mappers import (
    candidate_row_to_out,
    job_row_to_out,
    interview_row_to_out,
    note_row_to_out,
    opinion_row_to_out,
    pipeline_stage_row_to_out,
)
from app.modules.recruitment.infrastructure.providers import (
    DEFAULT_PIPELINE_STAGES,
    get_recruitment_setting_placeholder,
)
from app.modules.recruitment.infrastructure import queries as q


def _remove_accents(text: str) -> str:
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


# ─── Settings ─────────────────────────────────────────────────────────


class RecruitmentSettingsReader(IRecruitmentSettingsReader):
    def is_enabled(self, company_id: str) -> bool:
        return get_recruitment_setting_placeholder(company_id)


# ─── Jobs ──────────────────────────────────────────────────────────────


class JobRepository(IJobRepository):
    def get_by_id(self, company_id: str, job_id: str) -> Optional[dict[str, Any]]:
        res = (
            supabase.table("recruitment_jobs")
            .select("*")
            .eq("id", job_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return None
        return job_row_to_out(res.data, 0)

    def list_by_company(
        self, company_id: str, status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        return q.list_jobs_with_candidate_count(company_id, status)

    def create(self, company_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = {**data, "company_id": company_id}
        res = supabase.table("recruitment_jobs").insert(row).execute()
        if not res.data:
            raise ValueError("Erreur lors de la création du poste")
        return job_row_to_out(res.data[0], 0)

    def update(
        self, job_id: str, company_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        res = supabase.table("recruitment_jobs").update(data).eq("id", job_id).execute()
        j = res.data[0] if res.data else {}
        return job_row_to_out(j, 0)


# ─── Pipeline stages ───────────────────────────────────────────────────


class PipelineStageRepository(IPipelineStageRepository):
    def list_by_job(self, company_id: str, job_id: str) -> list[dict[str, Any]]:
        return q.get_pipeline_stages(company_id, job_id)

    def create_default_for_job(
        self, company_id: str, job_id: str
    ) -> list[dict[str, Any]]:
        stages = []
        for stage_def in DEFAULT_PIPELINE_STAGES:
            row = {"company_id": company_id, "job_id": job_id, **stage_def}
            res = supabase.table("recruitment_pipeline_stages").insert(row).execute()
            if res.data:
                stages.append(pipeline_stage_row_to_out(res.data[0]))
        return stages


# ─── Timeline ──────────────────────────────────────────────────────────


class TimelineEventWriter(ITimelineEventWriter):
    def add(
        self,
        company_id: str,
        candidate_id: str,
        event_type: str,
        description: str,
        actor_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        supabase.table("recruitment_timeline_events").insert(
            {
                "company_id": company_id,
                "candidate_id": candidate_id,
                "event_type": event_type,
                "description": description,
                "actor_id": actor_id,
                "metadata": metadata or {},
            }
        ).execute()


class TimelineEventReader(ITimelineEventReader):
    def list_by_candidate(
        self, company_id: str, candidate_id: str
    ) -> list[dict[str, Any]]:
        return q.list_timeline_events(company_id, candidate_id)


# ─── Candidates ───────────────────────────────────────────────────────


class CandidateRepository(ICandidateRepository):
    def get_by_id(self, company_id: str, candidate_id: str) -> Optional[dict[str, Any]]:
        return q.get_candidate(company_id, candidate_id)

    def list_by_company(
        self,
        company_id: str,
        job_id: Optional[str] = None,
        stage_id: Optional[str] = None,
        search: Optional[str] = None,
        participant_user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return q.list_candidates(
            company_id,
            job_id=job_id,
            stage_id=stage_id,
            search=search,
            participant_user_id=participant_user_id,
        )

    def create(self, company_id: str, data: dict[str, Any]) -> dict[str, Any]:
        row = {**data, "company_id": company_id}
        res = supabase.table("recruitment_candidates").insert(row).execute()
        if not res.data:
            raise ValueError("Erreur lors de la création du candidat")
        return candidate_row_to_out(res.data[0])

    def update(
        self, candidate_id: str, company_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        res = (
            supabase.table("recruitment_candidates")
            .update(data)
            .eq("id", candidate_id)
            .execute()
        )
        d = res.data[0] if res.data else {}
        return candidate_row_to_out(d)

    def delete(self, candidate_id: str, company_id: str) -> None:
        supabase.table("recruitment_candidates").delete().eq(
            "id", candidate_id
        ).execute()


# ─── Duplicate checker ────────────────────────────────────────────────


class DuplicateChecker(IDuplicateChecker):
    def check_duplicate_candidate(
        self,
        company_id: str,
        email: Optional[str],
        phone: Optional[str],
        exclude_candidate_id: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        if not email and not phone:
            return None
        if email:
            qq = (
                supabase.table("recruitment_candidates")
                .select("id, first_name, last_name, email, phone, job_id")
                .eq("company_id", company_id)
                .eq("email", email)
            )
            if exclude_candidate_id:
                qq = qq.neq("id", exclude_candidate_id)
            res = qq.limit(1).execute()
            if res.data:
                return res.data[0]
        if phone:
            qq = (
                supabase.table("recruitment_candidates")
                .select("id, first_name, last_name, email, phone, job_id")
                .eq("company_id", company_id)
                .eq("phone", phone)
            )
            if exclude_candidate_id:
                qq = qq.neq("id", exclude_candidate_id)
            res = qq.limit(1).execute()
            if res.data:
                return res.data[0]
        return None

    def check_duplicate_employee(
        self,
        company_id: str,
        email: Optional[str],
        phone: Optional[str],
    ) -> Optional[dict[str, Any]]:
        if not email:
            return None
        res = (
            supabase.table("employees")
            .select("id, first_name, last_name, email")
            .eq("company_id", company_id)
            .eq("email", email)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None


# ─── Participant checker ───────────────────────────────────────────────


class ParticipantChecker(IParticipantChecker):
    def is_participant(self, user_id: str, candidate_id: str) -> bool:
        res = (
            supabase.table("recruitment_interviews")
            .select("id, recruitment_interview_participants!inner(user_id)")
            .eq("candidate_id", candidate_id)
            .eq("recruitment_interview_participants.user_id", user_id)
            .limit(1)
            .execute()
        )
        return bool(res.data)


# ─── Employee creator (cross-module) ────────────────────────────────────


class EmployeeCreator(IEmployeeCreator):
    def __init__(self, timeline_writer: ITimelineEventWriter):
        self._timeline = timeline_writer

    def create_from_candidate(
        self,
        company_id: str,
        candidate_id: str,
        hire_date: str,
        site: Optional[str] = None,
        service: Optional[str] = None,
        job_title: Optional[str] = None,
        contract_type: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> dict[str, Any]:
        cand = (
            supabase.table("recruitment_candidates")
            .select("*, job:recruitment_jobs(title, contract_type, location)")
            .eq("id", candidate_id)
            .eq("company_id", company_id)
            .single()
            .execute()
        )
        if not cand.data:
            raise ValueError("Candidat non trouvé")
        c = cand.data
        job = c.get("job") or {}
        normalized_last = _remove_accents(c["last_name"]).upper()
        normalized_first = _remove_accents(c["first_name"]).capitalize()
        folder_name = f"{normalized_last}_{normalized_first}"
        username = (
            _remove_accents(c["first_name"]).lower().replace(" ", "_")
            + "."
            + _remove_accents(c["last_name"]).lower().replace(" ", "_")
        )
        employee_data = {
            "company_id": company_id,
            "first_name": c["first_name"],
            "last_name": c["last_name"],
            "email": c.get("email"),
            "hire_date": hire_date,
            "job_title": job_title or job.get("title"),
            "contract_type": contract_type or job.get("contract_type") or "CDI",
            "employment_status": "actif",
            "employee_folder_name": folder_name,
            "username": username,
        }
        res = supabase.table("employees").insert(employee_data).execute()
        if not res.data:
            raise ValueError("Erreur lors de la création du salarié")
        employee = res.data[0]
        supabase.table("recruitment_candidates").update(
            {
                "employee_id": employee["id"],
                "hired_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", candidate_id).execute()
        self._timeline.add(
            company_id=company_id,
            candidate_id=candidate_id,
            event_type="employee_created",
            description=f"Salarié créé : {c['first_name']} {c['last_name']}",
            actor_id=actor_id,
            metadata={"employee_id": employee["id"]},
        )
        return employee


# ─── Interviews ────────────────────────────────────────────────────────


class InterviewRepository(IInterviewRepository):
    def list_by_company(
        self,
        company_id: str,
        candidate_id: Optional[str] = None,
        participant_user_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        return q.list_interviews(
            company_id,
            candidate_id=candidate_id,
            participant_user_id=participant_user_id,
        )

    def create(
        self, company_id: str, user_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "company_id": company_id,
            "candidate_id": data["candidate_id"],
            "interview_type": data.get("interview_type") or "Entretien RH",
            "scheduled_at": data["scheduled_at"],
            "duration_minutes": data.get("duration_minutes") or 60,
            "location": data.get("location"),
            "meeting_link": data.get("meeting_link"),
            "created_by": user_id,
        }
        res = supabase.table("recruitment_interviews").insert(row).execute()
        if not res.data:
            raise ValueError("Erreur lors de la création de l'entretien")
        interview = res.data[0]
        for uid in data.get("participant_user_ids") or []:
            supabase.table("recruitment_interview_participants").insert(
                {
                    "interview_id": interview["id"],
                    "user_id": uid,
                    "role": "interviewer",
                }
            ).execute()
        return interview_row_to_out(interview)

    def update(
        self,
        interview_id: str,
        company_id: str,
        data: dict[str, Any],
        is_rh: bool,
    ) -> None:
        existing = (
            supabase.table("recruitment_interviews")
            .select("id, candidate_id")
            .eq("id", interview_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not existing or not existing.data:
            raise ValueError("Entretien non trouvé")
        if not is_rh:
            if data.get("summary") is not None:
                updates = {"summary": data["summary"]}
            else:
                raise ValueError("Accès non autorisé")
        else:
            updates = {k: v for k, v in data.items() if v is not None}
        if not updates:
            raise ValueError("Aucune modification")
        supabase.table("recruitment_interviews").update(updates).eq(
            "id", interview_id
        ).execute()


# ─── Notes ─────────────────────────────────────────────────────────────


class NoteRepository(INoteRepository):
    def list_by_candidate(
        self, company_id: str, candidate_id: str
    ) -> list[dict[str, Any]]:
        return q.list_notes(company_id, candidate_id)

    def create(
        self, company_id: str, author_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "company_id": company_id,
            "candidate_id": data["candidate_id"],
            "content": data["content"],
            "author_id": author_id,
        }
        res = supabase.table("recruitment_notes").insert(row).execute()
        if not res.data:
            raise ValueError("Erreur")
        return note_row_to_out(res.data[0])


# ─── Opinions ───────────────────────────────────────────────────────────


class OpinionRepository(IOpinionRepository):
    def list_by_candidate(
        self, company_id: str, candidate_id: str
    ) -> list[dict[str, Any]]:
        return q.list_opinions(company_id, candidate_id)

    def create(
        self, company_id: str, author_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "company_id": company_id,
            "candidate_id": data["candidate_id"],
            "rating": data["rating"],
            "comment": data.get("comment"),
            "author_id": author_id,
        }
        res = supabase.table("recruitment_opinions").insert(row).execute()
        if not res.data:
            raise ValueError("Erreur")
        return opinion_row_to_out(res.data[0])


# ─── Instances partagées (pour injection ou import direct) ───────────────

_settings_reader = RecruitmentSettingsReader()
_job_repo = JobRepository()
_pipeline_stage_repo = PipelineStageRepository()
_timeline_writer = TimelineEventWriter()
_timeline_reader = TimelineEventReader()
_candidate_repo = CandidateRepository()
_duplicate_checker = DuplicateChecker()
_participant_checker = ParticipantChecker()
_employee_creator = EmployeeCreator(_timeline_writer)
_interview_repo = InterviewRepository()
_note_repo = NoteRepository()
_opinion_repo = OpinionRepository()
