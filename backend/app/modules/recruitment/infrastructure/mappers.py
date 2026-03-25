# app/modules/recruitment/infrastructure/mappers.py
"""
Mappers Supabase/DB → dicts compatibles schémas responses (JobOut, CandidateOut, etc.).
Pas de dépendance FastAPI. Utilisés par repository et queries.
"""

from typing import Any, Optional


def candidate_row_to_out(
    row: dict[str, Any], stage: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Construit un dict compatible CandidateOut depuis une row (+ stage optionnel)."""
    s = (
        stage
        if stage is not None
        else (row.get("stage") if isinstance(row.get("stage"), dict) else {})
    )
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "job_id": row["job_id"],
        "current_stage_id": row.get("current_stage_id"),
        "current_stage_name": s.get("name") if s else None,
        "current_stage_type": s.get("stage_type") if s else None,
        "first_name": row["first_name"],
        "last_name": row["last_name"],
        "email": row.get("email"),
        "phone": row.get("phone"),
        "source": row.get("source"),
        "rejection_reason": row.get("rejection_reason"),
        "rejection_reason_detail": row.get("rejection_reason_detail"),
        "hired_at": str(row["hired_at"]) if row.get("hired_at") else None,
        "employee_id": row.get("employee_id"),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def job_row_to_out(row: dict[str, Any], candidate_count: int = 0) -> dict[str, Any]:
    """Construit un dict compatible JobOut depuis une row."""
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "title": row["title"],
        "description": row.get("description"),
        "location": row.get("location"),
        "contract_type": row.get("contract_type"),
        "status": row["status"],
        "tags": row.get("tags"),
        "created_by": row.get("created_by"),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "candidate_count": candidate_count,
    }


def pipeline_stage_row_to_out(row: dict[str, Any]) -> dict[str, Any]:
    """Construit un dict compatible PipelineStageOut depuis une row."""
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "name": row["name"],
        "position": row["position"],
        "is_final": row["is_final"],
        "stage_type": row["stage_type"],
    }


def interview_row_to_out(
    row: dict[str, Any],
    participants: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Construit un dict compatible InterviewOut depuis une row (+ participants optionnel)."""
    parts = participants
    if parts is None:
        raw = row.get("recruitment_interview_participants") or []
        parts = [
            {
                "user_id": p["user_id"],
                "role": p["role"],
                "first_name": (p.get("profiles") or {}).get("first_name"),
                "last_name": (p.get("profiles") or {}).get("last_name"),
            }
            for p in raw
        ]
    return {
        "id": row["id"],
        "candidate_id": row["candidate_id"],
        "interview_type": row["interview_type"],
        "scheduled_at": str(row["scheduled_at"]),
        "duration_minutes": row["duration_minutes"],
        "location": row.get("location"),
        "meeting_link": row.get("meeting_link"),
        "status": row["status"],
        "summary": row.get("summary"),
        "created_by": row.get("created_by"),
        "created_at": str(row["created_at"]),
        "participants": parts,
    }


def note_row_to_out(row: dict[str, Any]) -> dict[str, Any]:
    """Construit un dict compatible NoteOut depuis une row (avec author si jointure)."""
    author = row.get("author") or {}
    return {
        "id": row["id"],
        "candidate_id": row["candidate_id"],
        "content": row["content"],
        "author_id": row["author_id"],
        "author_first_name": author.get("first_name"),
        "author_last_name": author.get("last_name"),
        "created_at": str(row["created_at"]),
    }


def opinion_row_to_out(row: dict[str, Any]) -> dict[str, Any]:
    """Construit un dict compatible OpinionOut depuis une row (avec author si jointure)."""
    author = row.get("author") or {}
    return {
        "id": row["id"],
        "candidate_id": row["candidate_id"],
        "rating": row["rating"],
        "comment": row.get("comment"),
        "author_id": row["author_id"],
        "author_first_name": author.get("first_name"),
        "author_last_name": author.get("last_name"),
        "created_at": str(row["created_at"]),
    }


def timeline_event_row_to_out(row: dict[str, Any]) -> dict[str, Any]:
    """Construit un dict compatible TimelineEventOut depuis une row (avec actor si jointure)."""
    actor = row.get("actor") or {}
    return {
        "id": row["id"],
        "candidate_id": row["candidate_id"],
        "event_type": row["event_type"],
        "description": row["description"],
        "metadata": row.get("metadata"),
        "actor_id": row.get("actor_id"),
        "actor_first_name": actor.get("first_name"),
        "actor_last_name": actor.get("last_name"),
        "created_at": str(row["created_at"]),
    }
