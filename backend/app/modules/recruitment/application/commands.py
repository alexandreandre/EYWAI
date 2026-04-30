# app/modules/recruitment/application/commands.py
"""
Commandes (écritures) recruitment — délégation au service applicatif.
Comportement identique au legacy. Les routers appellent ces commandes.
"""

from typing import Any

from . import service as svc


def create_job(company_id: str, user_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Créer un job + pipeline par défaut. Lève ValueError en cas d'erreur."""
    return svc.service_create_job(company_id, user_id, data)


def update_job(job_id: str, company_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """Modifier un job. Lève ValueError si poste non trouvé ou aucune modification."""
    return svc.service_update_job(job_id, company_id, data)


def create_candidate(
    company_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Créer un candidat + événement timeline. Lève ValueError si poste non trouvé."""
    return svc.service_create_candidate(company_id, user_id, data)


def update_candidate(
    candidate_id: str, company_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Modifier un candidat. Lève ValueError si candidat non trouvé ou aucune modification."""
    return svc.service_update_candidate(candidate_id, company_id, data)


def delete_candidate(candidate_id: str, company_id: str) -> None:
    """Supprimer un candidat (autorisé seulement si position stage <= 1). Lève ValueError sinon."""
    svc.service_delete_candidate(candidate_id, company_id)


def move_candidate(
    candidate_id: str,
    company_id: str,
    stage_id: str,
    rejection_reason: str | None = None,
    rejection_reason_detail: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Déplacer un candidat vers une étape + timeline. Retourne stage_data. Lève ValueError si motif refus manquant."""
    return svc.service_move_candidate(
        candidate_id,
        company_id,
        stage_id,
        rejection_reason=rejection_reason,
        rejection_reason_detail=rejection_reason_detail,
        actor_id=actor_id,
    )


def create_interview(
    company_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Créer un entretien + participants + timeline. Lève ValueError si candidat non trouvé."""
    return svc.service_create_interview(company_id, user_id, data)


def update_interview(
    interview_id: str,
    company_id: str,
    data: dict[str, Any],
    is_rh: bool,
) -> None:
    """Modifier un entretien. Si non RH, seul summary autorisé. Lève ValueError si entretien non trouvé."""
    svc.service_update_interview(interview_id, company_id, data, is_rh)


def create_note(
    company_id: str, author_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Ajouter une note + timeline. Lève ValueError en cas d'erreur."""
    return svc.service_create_note(company_id, author_id, data)


def create_opinion(
    company_id: str, author_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Ajouter un avis (favorable/defavorable) + timeline. Lève ValueError si rating invalide."""
    return svc.service_create_opinion(company_id, author_id, data)


def hire_candidate(
    candidate_id: str,
    company_id: str,
    hire_date: str,
    site: str | None = None,
    service_name: str | None = None,
    job_title: str | None = None,
    contract_type: str | None = None,
    actor_id: str | None = None,
    link_to_employee_id: str | None = None,
    skip_duplicate_check: bool = False,
) -> dict[str, Any]:
    """Créer le salarié depuis le candidat + déplacement vers étape Recruté + timeline. Lève ValueError si candidat introuvable."""
    return svc.service_hire_candidate(
        candidate_id,
        company_id,
        hire_date,
        site=site,
        service_name=service_name,
        job_title=job_title,
        contract_type=contract_type,
        actor_id=actor_id,
        link_to_employee_id=link_to_employee_id,
        skip_duplicate_check=skip_duplicate_check,
    )


def archive_candidate(
    candidate_id: str, company_id: str, actor_id: str | None = None
) -> None:
    """Archiver un candidat (disparaît du pipeline actif). Lève ValueError si candidat introuvable."""
    svc.service_archive_candidate(candidate_id, company_id, actor_id=actor_id)


def create_pipeline_stage(
    company_id: str, job_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Ajoute une étape standard au pipeline. Lève ValueError si poste introuvable."""
    return svc.service_create_pipeline_stage(company_id, job_id, data)


def update_pipeline_stage(
    stage_id: str, company_id: str, job_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Met à jour le libellé (et options) d'une étape. Lève ValueError si introuvable."""
    return svc.service_update_pipeline_stage(stage_id, company_id, job_id, data)


def delete_pipeline_stage(stage_id: str, company_id: str, job_id: str) -> None:
    """Supprime une étape standard vide. Lève ValueError sinon."""
    svc.service_delete_pipeline_stage(stage_id, company_id, job_id)


def reorder_pipeline_stages(
    company_id: str, job_id: str, ordered_stage_ids: list[str]
) -> list[dict[str, Any]]:
    """Réordonne toutes les étapes du poste. Lève ValueError si la liste est invalide."""
    return svc.service_reorder_pipeline_stages(company_id, job_id, ordered_stage_ids)


def upload_candidate_cv(
    candidate_id: str,
    company_id: str,
    content: bytes,
    filename: str,
    content_type: str,
) -> str:
    """Upload du CV en storage ; retourne l'URL publique. Lève ValueError / RuntimeError."""
    return svc.service_upload_candidate_cv(
        candidate_id, company_id, content, filename, content_type
    )


def upload_note_audio(
    candidate_id: str,
    company_id: str,
    content: bytes,
    filename: str,
    content_type: str,
) -> str:
    """Upload audio de note ; retourne l'URL. Lève ValueError / RuntimeError."""
    return svc.service_upload_note_audio(
        candidate_id, company_id, content, filename, content_type
    )


def score_candidate_ai(candidate_id: str, company_id: str) -> dict[str, Any]:
    """
    Calcule et persiste le score IA ; retourne la ligne candidat enrichie (ai_score, etc.).
    Lève ValueError (métier), json.JSONDecodeError, RuntimeError.
    """
    return svc.service_score_candidate_ai(candidate_id, company_id)
