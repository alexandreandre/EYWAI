# app/modules/recruitment/application/service.py
"""
Service applicatif recruitment — orchestration uniquement.
Délègue au domain (règles pures) et à l'infrastructure (repository, queries, providers).
Aucun accès DB direct. Comportement identique au legacy.
"""

import logging
from typing import Any, Optional

from app.modules.recruitment.application.scoring_service import scoring_service
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
    analytics_repository,
)

_logger = logging.getLogger(__name__)


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


def _first_pipeline_stage_id(stages: list[dict[str, Any]]) -> Optional[str]:
    """Première étape « standard » par position, sinon première étape (ordre position)."""
    if not stages:
        return None
    by_pos = sorted(stages, key=lambda s: int(s.get("position") or 0))
    for s in by_pos:
        if s.get("stage_type") == "standard":
            return str(s["id"])
    return str(by_pos[0]["id"])


def service_create_candidate(
    company_id: str, user_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    job = _job_repo.get_by_id(company_id, data["job_id"])
    if not job:
        raise ValueError("Poste non trouvé")
    first_stages = _pipeline_stage_repo.list_by_job(company_id, data["job_id"])
    if not first_stages:
        first_stages = _pipeline_stage_repo.create_default_for_job(
            company_id, data["job_id"]
        )
    stage_id = _first_pipeline_stage_id(first_stages)
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
    locked_fields = {"first_name", "last_name", "email"}
    if locked_fields.intersection(data.keys()):
        cand = _candidate_repo.get_by_id(company_id, candidate_id)
        if cand and cand.get("hired_at"):
            raise ValueError(
                "Ce candidat a été recruté. Les champs identitaires ne peuvent plus être modifiés."
            )
    return _candidate_repo.update(candidate_id, company_id, data)


def service_archive_candidate(
    candidate_id: str, company_id: str, actor_id: Optional[str] = None
) -> None:
    cand = _candidate_repo.get_by_id(company_id, candidate_id)
    if not cand:
        raise ValueError("Candidat non trouvé")
    _candidate_repo.archive(candidate_id, company_id)
    _timeline_writer.add(
        company_id=company_id,
        candidate_id=candidate_id,
        event_type="archived",
        description=f"{cand['first_name']} {cand['last_name']} archivé",
        actor_id=actor_id,
    )


def service_delete_candidate(candidate_id: str, company_id: str) -> None:
    cand = infra_queries.get_candidate_with_stage_position(company_id, candidate_id)
    if not cand:
        raise ValueError("Candidat non trouvé")
    stage = cand.get("stage") or {}
    if not domain_rules.can_delete_candidate(stage.get("position", 0)):
        raise ValueError("Suppression du candidat non autorisée")
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
    if new_stage["stage_type"] == "hired" and not cand.get("employee_id"):
        raise ValueError(
            "Impossible de marquer ce candidat comme recruté sans finaliser l'embauche. "
            "Renseignez la date d'entrée et créez la fiche salarié."
        )
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
        description=f'{cand["first_name"]} {cand["last_name"]} déplacé vers "{new_stage["name"]}"',
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
        description=f'Entretien "{data.get("interview_type") or "Entretien RH"}" planifié le {data["scheduled_at"][:10]}',
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
    link_to_employee_id: Optional[str] = None,
    skip_duplicate_check: bool = False,
) -> dict[str, Any]:
    result = _employee_creator.create_from_candidate(
        company_id=company_id,
        candidate_id=candidate_id,
        hire_date=hire_date,
        site=site,
        service=service_name,
        job_title=job_title,
        contract_type=contract_type,
        actor_id=actor_id,
        link_to_employee_id=link_to_employee_id,
        skip_duplicate_check=skip_duplicate_check,
    )
    # Si un doublon salarié a été détecté, on retourne le signal sans déplacer l'étape
    if result.get("requires_confirmation"):
        return result
    # Déplacement atomique vers l'étape "hired" du pipeline
    cand = _candidate_repo.get_by_id(company_id, candidate_id)
    if cand:
        stages = _pipeline_stage_repo.list_by_job(company_id, cand["job_id"])
        hired_stage = next((s for s in stages if s["stage_type"] == "hired"), None)
        if hired_stage and cand.get("current_stage_id") != hired_stage["id"]:
            _candidate_repo.update(
                candidate_id, company_id, {"current_stage_id": hired_stage["id"]}
            )
    try:
        from app.modules.onboarding.infrastructure.repository import (
            onboarding_repository,
        )

        employee_id = result.get("id")
        if employee_id:
            onboarding_repository.create_checklist(
                employee_id=str(employee_id),
                company_id=company_id,
            )
            try:
                from app.modules.employees.application.account_provisioning import (
                    provision_collaborator_account,
                )

                prov = provision_collaborator_account(
                    str(employee_id),
                    company_id,
                    granted_by_user_id=actor_id,
                )
            except Exception as prov_err:
                _logger.error(
                    "[recruitment] Échec provisionnement compte/PDF identifiants : %s",
                    prov_err,
                )
            else:
                from app.modules.employees.infrastructure.repository import (
                    EmployeeRepository,
                )

                refreshed = EmployeeRepository().get_by_id(
                    str(employee_id), company_id
                )
                if refreshed:
                    result = refreshed
                if prov.get("generated_password"):
                    result["generated_password"] = prov["generated_password"]
                if prov.get("username"):
                    result["username"] = prov["username"]
                if prov.get("credentials_pdf_path"):
                    result["credentials_pdf_path"] = prov["credentials_pdf_path"]
    except Exception as e:

        _logger.error("[onboarding] Erreur création checklist : %s", e)
    return result


# ─── Queries (lectures via infrastructure) ─────────────────────────────


def service_list_jobs(
    company_id: str, status: Optional[str] = None
) -> list[dict[str, Any]]:
    return infra_queries.list_jobs_with_candidate_count(company_id, status)


def service_get_pipeline_stages(company_id: str, job_id: str) -> list[dict[str, Any]]:
    return infra_queries.get_pipeline_stages(company_id, job_id)


def _apply_positions(company_id: str, ordered_stages: list[dict[str, Any]]) -> None:
    """Applique les positions 0..n-1 en évitant les conflits de contrainte unique (job_id, position)."""
    for i, s in enumerate(ordered_stages):
        _pipeline_stage_repo.update(str(s["id"]), company_id, {"position": -(i + 1)})
    for i, s in enumerate(ordered_stages):
        _pipeline_stage_repo.update(str(s["id"]), company_id, {"position": i})


def _renormalize_stage_positions(company_id: str, job_id: str) -> None:
    """Recalcule les positions 0..n-1 : étapes standard puis refus puis recruté."""
    stages = _pipeline_stage_repo.list_by_job(company_id, job_id)
    standards = sorted(
        [s for s in stages if s.get("stage_type") == "standard"],
        key=lambda x: int(x.get("position") or 0),
    )
    rejected = sorted(
        [s for s in stages if s.get("stage_type") == "rejected"],
        key=lambda x: int(x.get("position") or 0),
    )
    hired = sorted(
        [s for s in stages if s.get("stage_type") == "hired"],
        key=lambda x: int(x.get("position") or 0),
    )
    ordered = standards + rejected + hired
    _apply_positions(company_id, ordered)


def service_create_pipeline_stage(
    company_id: str, job_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    if not _job_repo.get_by_id(company_id, job_id):
        raise ValueError("Poste non trouvé")
    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Le nom de l'étape est obligatoire.")
    row = {
        "name": name,
        "position": 9999,
        "stage_type": "standard",
        "is_final": False,
    }
    created = _pipeline_stage_repo.create(company_id, job_id, row)
    _renormalize_stage_positions(company_id, job_id)
    out = _pipeline_stage_repo.get_by_id(company_id, str(created["id"]))
    return out or created


def service_update_pipeline_stage(
    stage_id: str, company_id: str, job_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    stage = _pipeline_stage_repo.get_by_id(company_id, stage_id)
    if not stage or str(stage.get("job_id")) != str(job_id):
        raise ValueError("Étape non trouvée")
    raw = {k: v for k, v in data.items() if v is not None}
    if "name" in raw:
        raw["name"] = str(raw["name"]).strip()
        if not raw["name"]:
            raise ValueError("Le nom de l'étape est obligatoire.")
    st_type = stage.get("stage_type")
    if st_type in ("rejected", "hired"):
        updates = {k: v for k, v in raw.items() if k == "name"}
    else:
        updates = {k: v for k, v in raw.items() if k in ("name", "is_final")}
        if "is_final" in updates:
            updates["is_final"] = bool(updates["is_final"])
    if not updates:
        raise ValueError("Aucune modification")
    return _pipeline_stage_repo.update(stage_id, company_id, updates)


def service_delete_pipeline_stage(stage_id: str, company_id: str, job_id: str) -> None:
    stage = _pipeline_stage_repo.get_by_id(company_id, stage_id)
    if not stage or str(stage.get("job_id")) != str(job_id):
        raise ValueError("Étape non trouvée")
    if stage.get("stage_type") in ("rejected", "hired"):
        raise ValueError(
            "Les étapes finales « refus » et « recruté » ne peuvent pas être supprimées."
        )
    job_id = str(stage["job_id"])
    n = infra_queries.count_candidates_on_stage(company_id, stage_id)
    if n > 0:
        raise ValueError(
            "Impossible de supprimer une étape contenant encore des candidats. Déplacez-les d'abord."
        )
    _pipeline_stage_repo.delete(stage_id, company_id)
    _renormalize_stage_positions(company_id, job_id)


def service_reorder_pipeline_stages(
    company_id: str, job_id: str, ordered_stage_ids: list[str]
) -> list[dict[str, Any]]:
    if not _job_repo.get_by_id(company_id, job_id):
        raise ValueError("Poste non trouvé")
    stages = _pipeline_stage_repo.list_by_job(company_id, job_id)
    ids_set = {str(s["id"]) for s in stages}
    ordered = [str(x) for x in ordered_stage_ids]
    if len(ordered) != len(ids_set) or set(ordered) != ids_set:
        raise ValueError("La liste d'étapes ne correspond pas à ce poste.")
    by_id = {str(s["id"]): s for s in stages}
    ordered_stages = [by_id[sid] for sid in ordered]
    _apply_positions(company_id, ordered_stages)
    return _pipeline_stage_repo.list_by_job(company_id, job_id)


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


def service_list_notes(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    return _note_repo.list_by_candidate(company_id, candidate_id)


def service_list_opinions(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
    return _opinion_repo.list_by_candidate(company_id, candidate_id)


def service_get_timeline(company_id: str, candidate_id: str) -> list[dict[str, Any]]:
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
        warnings.append(
            {
                "type": "candidate",
                "existing_id": dup_cand["id"],
                "first_name": dup_cand.get("first_name"),
                "last_name": dup_cand.get("last_name"),
                "email": dup_cand.get("email"),
            }
        )
    dup_emp = _duplicate_checker.check_duplicate_employee(
        company_id, cand.get("email"), cand.get("phone")
    )
    if dup_emp:
        warnings.append(
            {
                "type": "employee",
                "existing_id": dup_emp["id"],
                "first_name": dup_emp.get("first_name"),
                "last_name": dup_emp.get("last_name"),
                "email": dup_emp.get("email"),
            }
        )
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
    return _duplicate_checker.check_duplicate_employee(company_id, email, phone)


def is_user_participant_for_candidate(user_id: str, candidate_id: str) -> bool:
    return _participant_checker.is_participant(user_id, candidate_id)


def service_get_recruitment_analytics(
    company_id: str,
    job_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    budget_total: Optional[float] = None,
) -> dict[str, Any]:
    return analytics_repository.get_analytics(
        company_id,
        job_id=job_id,
        date_from=date_from,
        date_to=date_to,
        budget_total=budget_total,
    )


def service_upload_candidate_cv(
    candidate_id: str,
    company_id: str,
    content: bytes,
    filename: str,
    content_type: str,
) -> str:
    return _candidate_repo.upload_cv(
        candidate_id,
        company_id,
        content,
        filename,
        content_type,
    )


def service_upload_note_audio(
    candidate_id: str,
    company_id: str,
    content: bytes,
    filename: str,
    content_type: str,
) -> str:
    return _note_repo.upload_audio(
        candidate_id,
        company_id,
        content,
        filename,
        content_type=content_type,
    )


def service_get_candidate_score_row(
    candidate_id: str, company_id: str
) -> Optional[dict[str, Any]]:
    return _candidate_repo.get_score_detail(candidate_id, company_id)


def service_score_candidate_ai(
    candidate_id: str, company_id: str
) -> dict[str, Any]:
    from app.modules.recruitment.application.cv_text_loader import load_cv_text

    cand = _candidate_repo.get_by_id(company_id, candidate_id)
    if not cand:
        raise ValueError("Candidat non trouvé")
    job = _job_repo.get_by_id(company_id, cand["job_id"])
    if not job:
        raise ValueError("Poste non trouvé")
    notes = _note_repo.list_by_candidate(company_id, candidate_id)
    opinions = _opinion_repo.list_by_candidate(company_id, candidate_id)
    interviews = _interview_repo.list_by_company(
        company_id, candidate_id=candidate_id
    )
    cv_text, cv_status = load_cv_text(cand.get("cv_url"))
    result = scoring_service.score_candidate(
        cand,
        job,
        notes,
        opinions,
        interviews=interviews,
        cv_text=cv_text,
        cv_status=cv_status,
    )
    _candidate_repo.save_score(
        candidate_id,
        company_id,
        int(result["score"]),
        result,
    )
    row = _candidate_repo.get_score_detail(candidate_id, company_id)
    if not row or row.get("ai_score") is None:
        raise RuntimeError("Échec de la persistance du score.")
    return row
