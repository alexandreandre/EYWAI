# app/modules/recruitment/application/service.py
"""
Service applicatif recruitment — orchestration uniquement.
Délègue au domain (règles pures) et à l'infrastructure (repository, queries, providers).
Aucun accès DB direct. Comportement identique au legacy.
"""
from typing import Any, Optional

from app.modules.recruitment.domain import rules as domain_rules
from app.modules.recruitment.infrastructure import queries as infra_queries
from app.modules.recruitment.infrastructure.providers import REJECTION_REASONS
from app.modules.recruitment.infrastructure.repository import (
    _candidate_repo,
    _duplicate_checker,
    _employee_creator,
    _interview_repo,
    _job_repo,
    _note_repo,
    _opinion_repo,
    _participant_checker,
    _pipeline_stage_repo,
    _settings_reader,
    _timeline_reader,
    _timeline_writer,
)


# ─── Settings (délégation infrastructure) ──────────────────────────────

def get_recruitment_setting(company_id: str) -> bool:
    return _settings_reader.is_enabled(company_id)


# ─── Commands (écritures via repository + rules) ───────────────────────

def service_create_job(
    company_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    row = {
        "title": data["title"],
        "description": data.get("description"),
        "location": data.get("location"),
        "contract_type": data.get("contract_type"),
        "status": data.get("status") or "draft",
        "tags": data.get("tags") or [],
        "created_by": user_id,
    }
    job = _job_repo.create(company_id, row)
    _pipeline_stage_repo.create_default_for_job(company_id, job["id"])
    return job


def service_update_job(
    job_id: str, company_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    existing = _job_repo.get_by_id(company_id, job_id)
    if not existing:
        raise ValueError("Poste non trouvé")
    updates = {k: v for k, v in data.items() if v is not None}
    if not updates:
        raise ValueError("Aucune modification")
    return _job_repo.update(job_id, company_id, updates)


def service_create_candidate(
    company_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    job = _job_repo.get_by_id(company_id, data["job_id"])
    if not job:
        raise ValueError("Poste non trouvé")
    first_stages = _pipeline_stage_repo.list_by_job(company_id, data["job_id"])
    stage_id = first_stages[0]["id"] if first_stages else None
    row = {
        "job_id": data["job_id"],
        "current_stage_id": stage_id,
        "first_name": data["first_name"],
        "last_name": data["last_name"],
        "email": data.get("email"),
        "phone": data.get("phone"),
        "source": data.get("source"),
        "created_by": user_id,
    }
    c = _candidate_repo.create(company_id, row)
    _timeline_writer.add(
        company_id=company_id,
        candidate_id=c["id"],
        event_type="candidate_created",
        description=f"Candidat créé : {c['first_name']} {c['last_name']}",
        actor_id=user_id,
    )
    return c


def service_update_candidate(
    candidate_id: str, company_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    return _candidate_repo.update(candidate_id, company_id, data)


def service_delete_candidate(candidate_id: str, company_id: str) -> None:
    cand = infra_queries.get_candidate_with_stage_position(company_id, candidate_id)
    if not cand:
        raise ValueError("Candidat non trouvé")
    stage = cand.get("stage") or {}
    if not domain_rules.can_delete_candidate(stage.get("position", 0)):
        raise ValueError(
            "Impossible de supprimer un candidat avancé dans le pipeline. Utilisez le refus."
        )
    _candidate_repo.delete(candidate_id, company_id)


def service_move_candidate(
    candidate_id: str,
    company_id: str,
    stage_id: str,
    rejection_reason: Optional[str] = None,
    rejection_reason_detail: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> dict[str, Any]:
    cand = _candidate_repo.get_by_id(company_id, candidate_id)
    if not cand:
        raise ValueError("Candidat non trouvé")
    stages = _pipeline_stage_repo.list_by_job(company_id, cand["job_id"])
    new_stage = next((s for s in stages if s["id"] == stage_id), None)
    if not new_stage:
        raise ValueError("Étape non trouvée")
    if not domain_rules.require_rejection_reason_for_rejected_stage(
        new_stage["stage_type"], rejection_reason
    ):
        raise ValueError("Un motif de refus est obligatoire.")
    updates = {"current_stage_id": stage_id}
    if new_stage["stage_type"] == "rejected":
        updates["rejection_reason"] = rejection_reason
        updates["rejection_reason_detail"] = rejection_reason_detail
    _candidate_repo.update(candidate_id, company_id, updates)
    event_type = "stage_changed"
    if new_stage["stage_type"] == "rejected":
        event_type = "rejected"
    elif new_stage["stage_type"] == "hired":
        event_type = "hired"
    _timeline_writer.add(
        company_id=company_id,
        candidate_id=candidate_id,
        event_type=event_type,
        description=f"{cand['first_name']} {cand['last_name']} déplacé vers \"{new_stage['name']}\"",
        actor_id=actor_id,
        metadata={"stage_id": stage_id, "stage_name": new_stage["name"]},
    )
    return new_stage


def service_create_interview(
    company_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    cand = _candidate_repo.get_by_id(company_id, data["candidate_id"])
    if not cand:
        raise ValueError("Candidat non trouvé")
    interview = _interview_repo.create(company_id, user_id, data)
    _timeline_writer.add(
        company_id=company_id,
        candidate_id=data["candidate_id"],
        event_type="interview_planned",
        description=f"Entretien \"{data.get('interview_type') or 'Entretien RH'}\" planifié le {data['scheduled_at'][:10]}",
        actor_id=user_id,
    )
    return interview


def service_update_interview(
    interview_id: str,
    company_id: str,
    data: dict[str, Any],
    is_rh: bool,
) -> None:
    _interview_repo.update(interview_id, company_id, data, is_rh)


def service_create_note(
    company_id: str, author_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    note = _note_repo.create(company_id, author_id, data)
    _timeline_writer.add(
        company_id=company_id,
        candidate_id=data["candidate_id"],
        event_type="note_added",
        description="Note ajoutée",
        actor_id=author_id,
    )
    return note


def service_create_opinion(
    company_id: str, author_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    if not domain_rules.is_valid_opinion_rating(data.get("rating", "")):
        raise ValueError("L'avis doit être 'favorable' ou 'defavorable'.")
    opinion = _opinion_repo.create(company_id, author_id, data)
    _timeline_writer.add(
        company_id=company_id,
        candidate_id=data["candidate_id"],
        event_type="opinion_added",
        description=f"Avis {'favorable' if data['rating'] == 'favorable' else 'défavorable'} donné",
        actor_id=author_id,
    )
    return opinion


def service_hire_candidate(
    candidate_id: str,
    company_id: str,
    hire_date: str,
    site: Optional[str] = None,
    service_name: Optional[str] = None,
    job_title: Optional[str] = None,
    contract_type: Optional[str] = None,
    actor_id: Optional[str] = None,
) -> dict[str, Any]:
    return _employee_creator.create_from_candidate(
        company_id=company_id,
        candidate_id=candidate_id,
        hire_date=hire_date,
        site=site,
        service=service_name,
        job_title=job_title,
        contract_type=contract_type,
        actor_id=actor_id,
    )


# ─── Queries (lectures via infrastructure) ─────────────────────────────

def service_list_jobs(
    company_id: str, status: Optional[str] = None
) -> list[dict[str, Any]]:
    return infra_queries.list_jobs_with_candidate_count(company_id, status)


def service_get_pipeline_stages(
    company_id: str, job_id: str
) -> list[dict[str, Any]]:
    return infra_queries.get_pipeline_stages(company_id, job_id)


def service_list_candidates(
    company_id: str,
    job_id: Optional[str] = None,
    stage_id: Optional[str] = None,
    search: Optional[str] = None,
    participant_user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    return infra_queries.list_candidates(
        company_id,
        job_id=job_id,
        stage_id=stage_id,
        search=search,
        participant_user_id=participant_user_id,
    )


def service_get_candidate(
    company_id: str, candidate_id: str
) -> Optional[dict[str, Any]]:
    return infra_queries.get_candidate(company_id, candidate_id)


def service_list_interviews(
    company_id: str,
    candidate_id: Optional[str] = None,
    participant_user_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    return _interview_repo.list_by_company(
        company_id,
        candidate_id=candidate_id,
        participant_user_id=participant_user_id,
    )


def service_list_notes(
    company_id: str, candidate_id: str
) -> list[dict[str, Any]]:
    return _note_repo.list_by_candidate(company_id, candidate_id)


def service_list_opinions(
    company_id: str, candidate_id: str
) -> list[dict[str, Any]]:
    return _opinion_repo.list_by_candidate(company_id, candidate_id)


def service_get_timeline(
    company_id: str, candidate_id: str
) -> list[dict[str, Any]]:
    return _timeline_reader.list_by_candidate(company_id, candidate_id)


def service_check_duplicate_warnings(
    company_id: str, candidate_id: str
) -> list[dict[str, Any]]:
    cand = infra_queries.get_candidate_email_phone(company_id, candidate_id)
    if not cand:
        raise ValueError("Candidat non trouvé")
    warnings = []
    dup_cand = _duplicate_checker.check_duplicate_candidate(
        company_id,
        cand.get("email"),
        cand.get("phone"),
        exclude_candidate_id=candidate_id,
    )
    if dup_cand:
        warnings.append({
            "type": "candidate",
            "existing_id": dup_cand["id"],
            "first_name": dup_cand.get("first_name"),
            "last_name": dup_cand.get("last_name"),
            "email": dup_cand.get("email"),
        })
    dup_emp = _duplicate_checker.check_duplicate_employee(
        company_id, cand.get("email"), cand.get("phone")
    )
    if dup_emp:
        warnings.append({
            "type": "employee",
            "existing_id": dup_emp["id"],
            "first_name": dup_emp.get("first_name"),
            "last_name": dup_emp.get("last_name"),
            "email": dup_emp.get("email"),
        })
    return warnings


def get_rejection_reasons_list() -> list[str]:
    return list(REJECTION_REASONS)


def check_duplicate_candidate(
    company_id: str,
    email: Optional[str],
    phone: Optional[str],
    exclude_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    return _duplicate_checker.check_duplicate_candidate(
        company_id, email, phone, exclude_candidate_id=exclude_id
    )


def check_duplicate_employee(
    company_id: str, email: Optional[str], phone: Optional[str]
) -> Optional[dict[str, Any]]:
    return _duplicate_checker.check_duplicate_employee(
        company_id, email, phone
    )


def is_user_participant_for_candidate(user_id: str, candidate_id: str) -> bool:
    return _participant_checker.is_participant(user_id, candidate_id)
