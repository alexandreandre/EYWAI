# app/modules/recruitment/infrastructure/queries.py
"""
Requêtes Supabase recruitment (lectures). Comportement identique au legacy.
Utilise core.config.supabase et les mappers pour retourner des dicts compatibles *Out.
"""
from typing import Any, Optional

from app.core.config import supabase

from app.modules.recruitment.infrastructure.mappers import (
    candidate_row_to_out,
    interview_row_to_out,
    job_row_to_out,
    note_row_to_out,
    opinion_row_to_out,
    pipeline_stage_row_to_out,
    timeline_event_row_to_out,
)


def list_jobs_with_candidate_count(
    company_id: str, status: Optional[str] = None
) -> list[dict[str, Any]]:
    """Liste des jobs avec candidate_count par poste."""
    q = supabase.table("recruitment_jobs").select("*").eq("company_id", company_id)
    if status:
        q = q.eq("status", status)
    q = q.order("created_at", desc=True)
    res = q.execute()
    jobs = res.data or []
    job_ids = [j["id"] for j in jobs]
    counts: dict[str, int] = {}
    if job_ids:
        for jid in job_ids:
            cnt = (
                supabase.table("recruitment_candidates")
                .select("id", count="exact")
                .eq("job_id", jid)
                .eq("company_id", company_id)
                .execute()
            )
            counts[jid] = cnt.count if cnt.count is not None else 0
    return [job_row_to_out(j, counts.get(j["id"], 0)) for j in jobs]


def get_pipeline_stages(company_id: str, job_id: str) -> list[dict[str, Any]]:
    """Liste des étapes du pipeline d'un job."""
    res = (
        supabase.table("recruitment_pipeline_stages")
        .select("*")
        .eq("job_id", job_id)
        .eq("company_id", company_id)
        .order("position")
        .execute()
    )
    return [pipeline_stage_row_to_out(s) for s in (res.data or [])]


def list_candidates(
    company_id: str,
    job_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    search: Optional[str] = None,
    participant_user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Liste des candidats avec filtres et filtre participant (collab)."""
    q = (
        supabase.table("recruitment_candidates")
        .select("*, stage:recruitment_pipeline_stages(name, stage_type)")
        .eq("company_id", company_id)
    )
    if job_id:
        q = q.eq("job_id", job_id)
    if stage_id:
        q = q.eq("current_stage_id", stage_id)
    q = q.order("created_at", desc=True)
    res = q.execute()
    candidates = res.data or []
    if search:
        s = search.lower()
        candidates = [
            c
            for c in candidates
            if s in (c.get("first_name", "") + " " + c.get("last_name", "")).lower()
            or s in (c.get("email") or "").lower()
            or s in (c.get("phone") or "").lower()
        ]
    if participant_user_id is not None:
        interviews = (
            supabase.table("recruitment_interviews")
            .select("candidate_id, recruitment_interview_participants!inner(user_id)")
            .eq("company_id", company_id)
            .eq("recruitment_interview_participants.user_id", participant_user_id)
            .execute()
        )
        participant_candidates = {i["candidate_id"] for i in (interviews.data or [])}
        candidates = [c for c in candidates if c["id"] in participant_candidates]
    return [candidate_row_to_out(c) for c in candidates]


def get_candidate(company_id: str, candidate_id: str) -> Optional[dict[str, Any]]:
    """Détail d'un candidat ou None."""
    res = (
        supabase.table("recruitment_candidates")
        .select("*, stage:recruitment_pipeline_stages(name, stage_type)")
        .eq("id", candidate_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    if not res.data:
        return None
    return candidate_row_to_out(res.data)


def get_candidate_with_stage_position(
    company_id: str, candidate_id: str
) -> Optional[dict[str, Any]]:
    """Récupère un candidat avec la position du stage (pour règle suppression)."""
    res = (
        supabase.table("recruitment_candidates")
        .select("id, current_stage_id, stage:recruitment_pipeline_stages(position)")
        .eq("id", candidate_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return res.data if res.data else None


def list_interviews(
    company_id: str,
    candidate_id: Optional[str] = None,
    participant_user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Liste des entretiens avec participants."""
    q = (
        supabase.table("recruitment_interviews")
        .select(
            "*, recruitment_interview_participants(user_id, role, profiles:user_id(first_name, last_name))"
        )
        .eq("company_id", company_id)
    )
    if candidate_id:
        q = q.eq("candidate_id", candidate_id)
    q = q.order("scheduled_at", desc=True)
    res = q.execute()
    interviews = res.data or []
    if participant_user_id is not None:
        interviews = [
            i
            for i in interviews
            if any(
                p.get("user_id") == participant_user_id
                for p in (i.get("recruitment_interview_participants") or [])
            )
        ]
    return [interview_row_to_out(i) for i in interviews]


def list_notes(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    """Notes d'un candidat."""
    res = (
        supabase.table("recruitment_notes")
        .select("*, author:profiles!author_id(first_name, last_name)")
        .eq("candidate_id", candidate_id)
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [note_row_to_out(n) for n in (res.data or [])]


def list_opinions(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    """Avis sur un candidat."""
    res = (
        supabase.table("recruitment_opinions")
        .select("*, author:profiles!author_id(first_name, last_name)")
        .eq("candidate_id", candidate_id)
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [opinion_row_to_out(o) for o in (res.data or [])]


def list_timeline_events(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    """Timeline d'un candidat."""
    res = (
        supabase.table("recruitment_timeline_events")
        .select("*, actor:profiles!actor_id(first_name, last_name)")
        .eq("candidate_id", candidate_id)
        .eq("company_id", company_id)
        .order("created_at", desc=True)
        .execute()
    )
    return [timeline_event_row_to_out(e) for e in (res.data or [])]


def get_candidate_email_phone(
    company_id: str, candidate_id: str
) -> Optional[dict[str, Any]]:
    """Récupère email et phone d'un candidat (pour check doublon)."""
    res = (
        supabase.table("recruitment_candidates")
        .select("email, phone")
        .eq("id", candidate_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return res.data if res.data else None
