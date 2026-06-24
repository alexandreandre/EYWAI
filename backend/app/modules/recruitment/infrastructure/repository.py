# app/modules/recruitment/infrastructure/repository.py
"""
Implémentations des interfaces domain (IJobRepository, etc.) avec Supabase.
Comportement identique au legacy. Accès DB via app.core.database.supabase.
"""

import json
import re
import unicodedata
import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
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


def _optional_uuid_str(value: Optional[str]) -> Optional[str]:
    """Retourne la chaîne UUID si valide, sinon None."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        uuid.UUID(s)
        return s
    except ValueError:
        return None


def _safe_cv_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    return (cleaned[:180] or "cv").lower()


BUCKET_RECRUITMENT_CVS = "recruitment-cvs"
BUCKET_RECRUITMENT_AUDIO = "recruitment-audio"


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

    def get_by_id(self, company_id: str, stage_id: str) -> Optional[dict[str, Any]]:
        res = (
            supabase.table("recruitment_pipeline_stages")
            .select("*")
            .eq("id", stage_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not res.data:
            return None
        return pipeline_stage_row_to_out(res.data)

    def create(
        self, company_id: str, job_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = {**data, "company_id": company_id, "job_id": job_id}
        res = supabase.table("recruitment_pipeline_stages").insert(row).execute()
        if not res.data:
            raise ValueError("Erreur lors de la création de l'étape")
        return pipeline_stage_row_to_out(res.data[0])

    def update(
        self, stage_id: str, company_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        res = (
            supabase.table("recruitment_pipeline_stages")
            .update(data)
            .eq("id", stage_id)
            .eq("company_id", company_id)
            .execute()
        )
        if not res.data:
            raise ValueError("Étape non trouvée")
        return pipeline_stage_row_to_out(res.data[0])

    def delete(self, stage_id: str, company_id: str) -> None:
        supabase.table("recruitment_pipeline_stages").delete().eq("id", stage_id).eq(
            "company_id", company_id
        ).execute()


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
        interviews = (
            supabase.table("recruitment_interviews")
            .select("id")
            .eq("candidate_id", candidate_id)
            .eq("company_id", company_id)
            .execute()
        )
        for row in interviews.data or []:
            supabase.table("recruitment_interview_participants").delete().eq(
                "interview_id", row["id"]
            ).execute()
        supabase.table("recruitment_interviews").delete().eq(
            "candidate_id", candidate_id
        ).eq("company_id", company_id).execute()
        supabase.table("recruitment_notes").delete().eq(
            "candidate_id", candidate_id
        ).eq("company_id", company_id).execute()
        supabase.table("recruitment_opinions").delete().eq(
            "candidate_id", candidate_id
        ).eq("company_id", company_id).execute()
        supabase.table("recruitment_timeline_events").delete().eq(
            "candidate_id", candidate_id
        ).eq("company_id", company_id).execute()
        supabase.table("recruitment_candidates").delete().eq(
            "id", candidate_id
        ).eq("company_id", company_id).execute()

    def archive(self, candidate_id: str, company_id: str) -> None:
        supabase.table("recruitment_candidates").update({"is_archived": True}).eq(
            "id", candidate_id
        ).eq("company_id", company_id).execute()

    def upload_cv(
        self,
        candidate_id: str,
        company_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        exists = (
            supabase.table("recruitment_candidates")
            .select("id")
            .eq("id", candidate_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not exists.data:
            raise ValueError("Candidat non trouvé")
        safe_name = _safe_cv_filename(filename)
        path = f"{company_id}/{candidate_id}/{safe_name}"
        supabase.storage.from_(BUCKET_RECRUITMENT_CVS).upload(
            path,
            file_bytes,
            file_options={"content-type": content_type, "x-upsert": "true"},
        )
        signed_r = supabase.storage.from_(BUCKET_RECRUITMENT_CVS).create_signed_url(
            path,
            31536000,
            options={"download": True},
        )
        signed_url: Optional[str] = None
        if isinstance(signed_r, dict):
            signed_url = signed_r.get("signedURL") or signed_r.get("signedUrl")
        if not signed_url:
            raise RuntimeError("Impossible de générer l'URL signée du CV.")
        supabase.table("recruitment_candidates").update({"cv_url": signed_url}).eq(
            "id", candidate_id
        ).eq("company_id", company_id).execute()
        return signed_url

    def save_score(
        self,
        candidate_id: str,
        company_id: str,
        score: int,
        score_detail: dict[str, Any],
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        supabase.table("recruitment_candidates").update(
            {
                "ai_score": score,
                "ai_score_detail": score_detail,
                "ai_scored_at": now,
            }
        ).eq("id", candidate_id).eq("company_id", company_id).execute()

    def get_score_detail(
        self, candidate_id: str, company_id: str
    ) -> Optional[dict[str, Any]]:
        res = (
            supabase.table("recruitment_candidates")
            .select("ai_score, ai_score_detail, ai_scored_at")
            .eq("id", candidate_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        return res.data if res.data else None


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
        statut: Optional[str] = None,
        contract_end_date: Optional[str] = None,
        date_debut_execution: Optional[str] = None,
        date_conclusion_contrat: Optional[str] = None,
        maintien_regime_apprenti: bool = False,
        actor_id: Optional[str] = None,
        link_to_employee_id: Optional[str] = None,
        skip_duplicate_check: bool = False,
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

        # Cas : lier à un salarié existant sans en créer un nouveau
        if link_to_employee_id:
            existing = (
                supabase.table("employees")
                .select("id, first_name, last_name")
                .eq("id", link_to_employee_id)
                .eq("company_id", company_id)
                .maybe_single()
                .execute()
            )
            if not existing.data:
                raise ValueError("Salarié existant non trouvé")
            employee = existing.data
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
                description=f"Candidat lié au salarié existant : {employee['first_name']} {employee['last_name']}",
                actor_id=actor_id,
                metadata={"employee_id": employee["id"], "linked": True},
            )
            return employee

        # Vérifier si un salarié avec le même email existe déjà (sauf si bypass explicite)
        candidate_email = c.get("email")
        if candidate_email and not skip_duplicate_check:
            dup = (
                supabase.table("employees")
                .select("id, first_name, last_name, email")
                .eq("company_id", company_id)
                .eq("email", candidate_email)
                .limit(1)
                .execute()
            )
            if dup.data:
                existing_emp = dup.data[0]
                # Retourner un signal de confirmation requis
                return {
                    "requires_confirmation": True,
                    "existing_employee_id": existing_emp["id"],
                    "existing_employee_first_name": existing_emp["first_name"],
                    "existing_employee_last_name": existing_emp["last_name"],
                    "existing_employee_email": existing_emp["email"],
                }

        normalized_last = _remove_accents(c["last_name"]).upper()
        normalized_first = _remove_accents(c["first_name"]).capitalize()
        folder_name = f"{normalized_last}_{normalized_first}"
        from app.modules.employees.infrastructure.queries import allocate_collaborator_username

        username = allocate_collaborator_username(c["first_name"], c["last_name"])
        employee_data = {
            "company_id": company_id,
            "first_name": c["first_name"],
            "last_name": c["last_name"],
            "email": candidate_email,
            "hire_date": hire_date,
            "job_title": job_title or job.get("title"),
            "contract_type": contract_type or job.get("contract_type") or "CDI",
            "statut": statut or "Non-Cadre",
            "employment_status": "en_onboarding",
            "employee_folder_name": folder_name,
            "username": username,
        }
        if contract_end_date:
            employee_data["contract_end_date"] = contract_end_date
        if date_debut_execution:
            employee_data["date_debut_execution"] = date_debut_execution
        if date_conclusion_contrat:
            employee_data["date_conclusion_contrat"] = date_conclusion_contrat
        if maintien_regime_apprenti:
            employee_data["specificites_paie"] = {
                "maintien_regime_apprenti": True,
            }
        svc_id = _optional_uuid_str(service)
        if svc_id:
            employee_data["service_id"] = svc_id
        try:
            res = supabase.table("employees").insert(employee_data).execute()
        except Exception as insert_err:
            err_msg = str(insert_err)
            if (
                "employees_employment_status_check" in err_msg
                and employee_data.get("employment_status") == "en_onboarding"
            ):
                employee_data = dict(employee_data)
                employee_data["employment_status"] = "actif"
                res = supabase.table("employees").insert(employee_data).execute()
            else:
                raise
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

    def upload_audio(
        self,
        candidate_id: str,
        company_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str = "audio/webm",
    ) -> str:
        exists = (
            supabase.table("recruitment_candidates")
            .select("id")
            .eq("id", candidate_id)
            .eq("company_id", company_id)
            .maybe_single()
            .execute()
        )
        if not exists.data:
            raise ValueError("Candidat non trouvé")
        safe_name = _safe_cv_filename(filename)
        path = f"{company_id}/{candidate_id}/{safe_name}"
        supabase.storage.from_(BUCKET_RECRUITMENT_AUDIO).upload(
            path,
            file_bytes,
            file_options={"content-type": content_type, "x-upsert": "true"},
        )
        signed_r = supabase.storage.from_(BUCKET_RECRUITMENT_AUDIO).create_signed_url(
            path,
            31536000,
            options={"download": True},
        )
        signed_url: Optional[str] = None
        if isinstance(signed_r, dict):
            signed_url = signed_r.get("signedURL") or signed_r.get("signedUrl")
        if not signed_url:
            raise RuntimeError("Impossible de générer l'URL signée de l'audio.")
        return signed_url

    def create(
        self, company_id: str, author_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        row = {
            "company_id": company_id,
            "candidate_id": data["candidate_id"],
            "content": data["content"],
            "author_id": author_id,
        }
        if data.get("audio_url"):
            row["audio_url"] = data["audio_url"]
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


# ─── Analytics ───────────────────────────────────────────────────────


def _analytics_parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    s = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _analytics_metadata_dict(md: Any) -> dict[str, Any]:
    if md is None:
        return {}
    if isinstance(md, dict):
        return md
    if isinstance(md, str):
        try:
            return json.loads(md)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


class AnalyticsRepository:
    """Agrégations recrutement (time-to-hire, sources, funnel, coût / embauche)."""

    def get_analytics(
        self,
        company_id: str,
        job_id: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        budget_total: Optional[float] = None,
    ) -> dict[str, Any]:
        cq = (
            supabase.table("recruitment_candidates")
            .select(
                "id, job_id, current_stage_id, source, hired_at, created_at, "
                "is_archived, rejection_reason"
            )
            .eq("company_id", company_id)
        )
        if job_id:
            cq = cq.eq("job_id", job_id)
        if date_from:
            cq = cq.gte("created_at", f"{date_from}T00:00:00+00:00")
        if date_to:
            cq = cq.lte("created_at", f"{date_to}T23:59:59.999999+00:00")
        cand_res = cq.execute()
        candidates: list[dict[str, Any]] = cand_res.data or []

        jq = (
            supabase.table("recruitment_jobs")
            .select("id, title")
            .eq("company_id", company_id)
        )
        if job_id:
            jq = jq.eq("id", job_id)
        jobs = jq.execute().data or []
        job_titles = {str(j["id"]): str(j.get("title") or "") for j in jobs}

        sq = (
            supabase.table("recruitment_pipeline_stages")
            .select("id, job_id, name, position, stage_type")
            .eq("company_id", company_id)
        )
        if job_id:
            sq = sq.eq("job_id", job_id)
        stages = sq.execute().data or []
        stages_sorted = sorted(
            stages,
            key=lambda s: (str(s.get("job_id")), int(s.get("position") or 0)),
        )

        cand_ids = [str(c["id"]) for c in candidates]
        events: list[dict[str, Any]] = []
        if cand_ids:
            event_types = ["stage_changed", "hired", "rejected", "employee_created"]
            for batch in (
                cand_ids[i : i + 80] for i in range(0, len(cand_ids), 80)
            ):
                tq = (
                    supabase.table("recruitment_timeline_events")
                    .select("candidate_id, event_type, created_at, metadata")
                    .eq("company_id", company_id)
                    .in_("candidate_id", batch)
                    .in_("event_type", event_types)
                    .execute()
                )
                events.extend(tq.data or [])

        total_candidates = len(candidates)
        hired_list = [c for c in candidates if c.get("hired_at")]
        total_hired = len(hired_list)
        overall_conversion_rate = (
            (total_hired / total_candidates * 100.0) if total_candidates else 0.0
        )

        tth_days: list[float] = []
        for c in hired_list:
            created = _analytics_parse_ts(c.get("created_at"))
            hired = _analytics_parse_ts(c.get("hired_at"))
            if created and hired:
                delta = (hired - created).total_seconds() / 86400.0
                tth_days.append(max(0.0, delta))
        avg_time_to_hire_days = (
            sum(tth_days) / len(tth_days) if tth_days else 0.0
        )

        hired_by_job: dict[str, list[float]] = defaultdict(list)
        for c in hired_list:
            jid = str(c.get("job_id") or "")
            created = _analytics_parse_ts(c.get("created_at"))
            hired = _analytics_parse_ts(c.get("hired_at"))
            if not jid or not created or not hired:
                continue
            delta = (hired - created).total_seconds() / 86400.0
            hired_by_job[jid].append(max(0.0, delta))

        time_to_hire_by_job: list[dict[str, Any]] = []
        for jid, days_list in hired_by_job.items():
            if not days_list:
                continue
            time_to_hire_by_job.append(
                {
                    "job_id": jid,
                    "job_title": job_titles.get(jid, ""),
                    "avg_days": sum(days_list) / len(days_list),
                    "min_days": float(min(days_list)),
                    "max_days": float(max(days_list)),
                    "nb_hired": len(days_list),
                }
            )
        time_to_hire_by_job.sort(key=lambda x: x["avg_days"], reverse=True)

        by_source: dict[str, dict[str, int]] = defaultdict(
            lambda: {"nb_candidates": 0, "nb_hired": 0}
        )
        for c in candidates:
            raw = (c.get("source") or "").strip()
            src = raw if raw else "Direct"
            by_source[src]["nb_candidates"] += 1
            if c.get("hired_at"):
                by_source[src]["nb_hired"] += 1
        source_stats: list[dict[str, Any]] = []
        for src, v in sorted(
            by_source.items(), key=lambda x: -x[1]["nb_candidates"]
        ):
            nb_c = v["nb_candidates"]
            nb_h = v["nb_hired"]
            source_stats.append(
                {
                    "source": src,
                    "nb_candidates": nb_c,
                    "nb_hired": nb_h,
                    "conversion_rate": (nb_h / nb_c * 100.0) if nb_c else 0.0,
                }
            )

        events_by_cand: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for e in events:
            cid = str(e.get("candidate_id") or "")
            if cid:
                events_by_cand[cid].append(e)
        for lst in events_by_cand.values():
            lst.sort(
                key=lambda x: _analytics_parse_ts(x.get("created_at"))
                or datetime.min.replace(tzinfo=timezone.utc)
            )

        stages_by_job: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for s in stages_sorted:
            stages_by_job[str(s.get("job_id") or "")].append(s)
        for lst in stages_by_job.values():
            lst.sort(key=lambda x: int(x.get("position") or 0))

        stage_durations: dict[str, list[float]] = defaultdict(list)

        def _stage_index(job_stages: list[dict[str, Any]], sid: str) -> int:
            for i, st in enumerate(job_stages):
                if str(st.get("id")) == sid:
                    return i
            return -1

        for c in candidates:
            cid = str(c.get("id") or "")
            jid = str(c.get("job_id") or "")
            job_stages = stages_by_job.get(jid, [])
            if not job_stages:
                continue
            created = _analytics_parse_ts(c.get("created_at"))
            evs = events_by_cand.get(cid, [])
            seq: list[tuple[datetime, str]] = []
            for e in evs:
                md = _analytics_metadata_dict(e.get("metadata"))
                sid = md.get("stage_id")
                if not sid:
                    continue
                ts = _analytics_parse_ts(e.get("created_at"))
                if ts:
                    seq.append((ts, str(sid)))
            if created and seq:
                first_ts, first_sid = seq[0]
                initial_sid = str(job_stages[0].get("id"))
                dur0 = (first_ts - created).total_seconds() / 86400.0
                if dur0 >= 0:
                    stage_durations[initial_sid].append(dur0)
            for i in range(len(seq) - 1):
                t0, sid0 = seq[i]
                t1, _sid1 = seq[i + 1]
                ddays = (t1 - t0).total_seconds() / 86400.0
                if ddays >= 0:
                    stage_durations[str(sid0)].append(ddays)

        stage_conversion: list[dict[str, Any]] = []
        job_ids_for_stages = sorted(
            {str(c.get("job_id")) for c in candidates if c.get("job_id")}
            | {str(j["id"]) for j in jobs},
            key=lambda x: (job_titles.get(x, "") or x),
        )
        for jid in job_ids_for_stages:
            job_stages = stages_by_job.get(jid, [])
            if not job_stages:
                continue
            job_cands = [c for c in candidates if str(c.get("job_id")) == jid]
            max_idx_by_cand: list[int] = []
            for c in job_cands:
                cid = str(c.get("id"))
                cur_sid = c.get("current_stage_id")
                cur_i = _stage_index(job_stages, str(cur_sid)) if cur_sid else -1
                mx = cur_i
                for e in events_by_cand.get(cid, []):
                    md = _analytics_metadata_dict(e.get("metadata"))
                    sid = md.get("stage_id")
                    if sid:
                        idx = _stage_index(job_stages, str(sid))
                        mx = max(mx, idx)
                max_idx_by_cand.append(mx)

            title_prefix = job_titles.get(jid, "")
            n_st = len(job_stages)
            for pos, st in enumerate(job_stages):
                idx = pos
                nb_cand_at = sum(1 for m in max_idx_by_cand if m >= idx)
                nb_pass = (
                    sum(1 for m in max_idx_by_cand if m >= idx + 1)
                    if pos < n_st - 1
                    else 0
                )
                conv = (nb_pass / nb_cand_at * 100.0) if nb_cand_at else 0.0
                sid = str(st.get("id") or "")
                durs = stage_durations.get(sid, [])
                avg_st = sum(durs) / len(durs) if durs else 0.0
                st_name = str(st.get("name") or "")
                if not job_id and title_prefix:
                    disp_name = f"{title_prefix} — {st_name}"
                else:
                    disp_name = st_name
                stage_conversion.append(
                    {
                        "stage_name": disp_name,
                        "stage_position": int(st.get("position") or pos),
                        "nb_candidates": nb_cand_at,
                        "nb_passed": nb_pass,
                        "conversion_rate": conv,
                        "avg_days_in_stage": avg_st,
                    }
                )

        cost_per_hire: Optional[float] = None
        if budget_total is not None and total_hired > 0:
            cost_per_hire = float(budget_total) / float(total_hired)

        period_start: Optional[date] = None
        period_end: Optional[date] = None
        if date_from:
            try:
                period_start = date.fromisoformat(date_from[:10])
            except ValueError:
                period_start = None
        if date_to:
            try:
                period_end = date.fromisoformat(date_to[:10])
            except ValueError:
                period_end = None

        return {
            "period_start": period_start,
            "period_end": period_end,
            "total_candidates": total_candidates,
            "total_hired": total_hired,
            "overall_conversion_rate": overall_conversion_rate,
            "avg_time_to_hire_days": avg_time_to_hire_days,
            "time_to_hire_by_job": time_to_hire_by_job,
            "source_stats": source_stats,
            "stage_conversion": stage_conversion,
            "cost_per_hire": cost_per_hire,
        }


analytics_repository = AnalyticsRepository()


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
