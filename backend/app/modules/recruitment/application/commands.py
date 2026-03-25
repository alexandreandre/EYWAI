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
) -> dict[str, Any]:
    """Créer le salarié depuis le candidat + mise à jour candidat + timeline. Lève ValueError si candidat introuvable."""
    return svc.service_hire_candidate(
        candidate_id,
        company_id,
        hire_date,
        site=site,
        service_name=service_name,
        job_title=job_title,
        contract_type=contract_type,
        actor_id=actor_id,
    )
