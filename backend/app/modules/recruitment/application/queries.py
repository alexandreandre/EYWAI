# app/modules/recruitment/application/queries.py
"""
Requêtes (lectures) recruitment — délégation au service applicatif.
Comportement identique au legacy. Les routers appellent ces requêtes.
"""

from typing import Any, Optional

from . import service as svc


def get_recruitment_settings(company_id: str) -> dict[str, Any]:
    """Indique si le module est activé pour l'entreprise. Retourne {"enabled": bool}."""
    return {"enabled": svc.get_recruitment_setting(company_id)}


def list_jobs(company_id: str, status: Optional[str] = None) -> list[dict[str, Any]]:
    """Liste des postes avec candidate_count. Liste de dicts compatibles JobOut."""
    return svc.service_list_jobs(company_id, status)


def get_pipeline_stages(company_id: str, job_id: str) -> list[dict[str, Any]]:
    """Étapes du pipeline d'un job. Liste de dicts compatibles PipelineStageOut."""
    return svc.service_get_pipeline_stages(company_id, job_id)


def list_candidates(
    company_id: str,
    job_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    search: Optional[str] = None,
    participant_user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Liste des candidats (filtres + filtre collab participant). Liste de dicts compatibles CandidateOut."""
    return svc.service_list_candidates(
        company_id,
        job_id=job_id,
        stage_id=stage_id,
        search=search,
        participant_user_id=participant_user_id,
    )


def get_candidate(company_id: str, candidate_id: str) -> Optional[dict[str, Any]]:
    """Détail d'un candidat. Dict compatible CandidateOut ou None si non trouvé."""
    return svc.service_get_candidate(company_id, candidate_id)


def list_interviews(
    company_id: str,
    candidate_id: Optional[str] = None,
    participant_user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Liste des entretiens. Liste de dicts compatibles InterviewOut."""
    return svc.service_list_interviews(
        company_id,
        candidate_id=candidate_id,
        participant_user_id=participant_user_id,
    )


def list_notes(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    """Notes d'un candidat. Liste de dicts compatibles NoteOut."""
    return svc.service_list_notes(company_id, candidate_id)


def list_opinions(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    """Avis sur un candidat. Liste de dicts compatibles OpinionOut."""
    return svc.service_list_opinions(company_id, candidate_id)


def get_timeline(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    """Timeline d'un candidat. Liste de dicts compatibles TimelineEventOut."""
    return svc.service_get_timeline(company_id, candidate_id)


def get_rejection_reasons() -> list[str]:
    """Liste des motifs de refus (statique)."""
    return svc.get_rejection_reasons_list()


def check_duplicate(company_id: str, candidate_id: str) -> dict[str, Any]:
    """Avertissements doublon candidat / salarié. Retourne {"warnings": [DuplicateWarning, ...]}. Lève ValueError si candidat non trouvé."""
    warnings = svc.service_check_duplicate_warnings(company_id, candidate_id)
    return {"warnings": warnings}


def is_user_participant_for_candidate(user_id: str, candidate_id: str) -> bool:
    """Vérifie si l'utilisateur est participant (intervieweur) pour le candidat."""
    return svc.is_user_participant_for_candidate(user_id, candidate_id)
