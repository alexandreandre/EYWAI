# app/modules/recruitment/api/router.py
"""
Router API recruitment — délégation exclusive à la couche application.
Pas de logique métier lourde : auth, validation schémas, appel commands/queries, mapping erreurs → HTTP.
Comportement HTTP identique au legacy api/routers/recruitment.py.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import get_current_user
from app.modules.users.schemas.responses import User

from app.modules.recruitment.application import commands, queries
from app.modules.recruitment.schemas import (
    CandidateCreate,
    CandidateOut,
    CandidateUpdate,
    DuplicateWarning,
    HireCandidateBody,
    InterviewCreate,
    InterviewOut,
    InterviewUpdate,
    JobCreate,
    JobOut,
    JobUpdate,
    MoveCandidateBody,
    NoteCreate,
    NoteOut,
    OpinionCreate,
    OpinionOut,
    PipelineStageOut,
    TimelineEventOut,
)

router = APIRouter(prefix="/api/recruitment", tags=["Recruitment"])


# ─── Helpers (auth / contexte, pas de logique métier) ──────────────────

def _company_id(current_user: User) -> Optional[str]:
    return getattr(current_user, "active_company_id", None) or (
        current_user.accessible_companies[0].company_id
        if current_user.accessible_companies
        else None
    )


def _ensure_module_enabled(current_user: User) -> str:
    company_id = _company_id(current_user)
    if not company_id:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    if not queries.get_recruitment_settings(str(company_id)).get("enabled", False):
        raise HTTPException(
            status_code=403,
            detail="Le module Recrutement n'est pas activé pour cette entreprise.",
        )
    return str(company_id)


def _ensure_rh_access(current_user: User, company_id: str) -> None:
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas l'autorisation d'accéder à ces candidatures.",
        )


def _ensure_collab_or_rh(current_user: User, company_id: str, candidate_id: str) -> None:
    if current_user.has_rh_access_in_company(company_id):
        return
    if not queries.is_user_participant_for_candidate(str(current_user.id), candidate_id):
        raise HTTPException(
            status_code=403,
            detail="Vous n'avez pas l'autorisation d'accéder à ces candidatures.",
        )


def _value_error_to_http(e: ValueError) -> HTTPException:
    msg = str(e)
    if "non trouvé" in msg or "non trouvée" in msg:
        return HTTPException(status_code=404, detail=msg)
    if "Accès non autorisé" in msg:
        return HTTPException(status_code=403, detail=msg)
    return HTTPException(status_code=400, detail=msg)


# ─── Settings ──────────────────────────────────────────────────────────

@router.get("/settings")
def get_recruitment_settings(current_user: User = Depends(get_current_user)):
    company_id = _company_id(current_user)
    if not company_id:
        return {"enabled": False}
    return queries.get_recruitment_settings(str(company_id))


# ─── JOBS ─────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=List[JobOut])
def list_jobs(
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    data = queries.list_jobs(company_id, status)
    return [JobOut(**x) for x in data]


@router.post("/jobs", response_model=JobOut)
def create_job(
    body: JobCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        out = commands.create_job(
            company_id, str(current_user.id), body.model_dump()
        )
        return JobOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


@router.patch("/jobs/{job_id}", response_model=JobOut)
def update_job(
    job_id: str,
    body: JobUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        out = commands.update_job(
            job_id, company_id,
            {k: v for k, v in body.model_dump().items() if v is not None},
        )
        return JobOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


# ─── PIPELINE STAGES ───────────────────────────────────────────────────

@router.get("/jobs/{job_id}/stages", response_model=List[PipelineStageOut])
def get_pipeline_stages(
    job_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    data = queries.get_pipeline_stages(company_id, job_id)
    return [PipelineStageOut(**x) for x in data]


# ─── CANDIDATES ───────────────────────────────────────────────────────

@router.get("/candidates", response_model=List[CandidateOut])
def list_candidates(
    job_id: Optional[str] = Query(None),
    stage_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    is_rh = current_user.has_rh_access_in_company(company_id)
    participant_user_id = None if is_rh else str(current_user.id)
    data = queries.list_candidates(
        company_id,
        job_id=job_id,
        stage_id=stage_id,
        search=search,
        participant_user_id=participant_user_id,
    )
    return [CandidateOut(**x) for x in data]


@router.post("/candidates", response_model=CandidateOut)
def create_candidate(
    body: CandidateCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        out = commands.create_candidate(
            company_id, str(current_user.id), body.model_dump()
        )
        return CandidateOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


@router.get("/candidates/{candidate_id}", response_model=CandidateOut)
def get_candidate(
    candidate_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_collab_or_rh(current_user, company_id, candidate_id)
    out = queries.get_candidate(company_id, candidate_id)
    if not out:
        raise HTTPException(status_code=404, detail="Candidat non trouvé")
    return CandidateOut(**out)


@router.patch("/candidates/{candidate_id}", response_model=CandidateOut)
def update_candidate(
    candidate_id: str,
    body: CandidateUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        out = commands.update_candidate(
            candidate_id, company_id,
            {k: v for k, v in body.model_dump().items() if v is not None},
        )
        return CandidateOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


@router.delete("/candidates/{candidate_id}")
def delete_candidate(
    candidate_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        commands.delete_candidate(candidate_id, company_id)
        return {"ok": True}
    except ValueError as e:
        raise _value_error_to_http(e)


@router.post("/candidates/{candidate_id}/move")
def move_candidate(
    candidate_id: str,
    body: MoveCandidateBody,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        stage = commands.move_candidate(
            candidate_id,
            company_id,
            body.stage_id,
            rejection_reason=body.rejection_reason,
            rejection_reason_detail=body.rejection_reason_detail,
            actor_id=str(current_user.id),
        )
        return {"ok": True, "stage": stage}
    except ValueError as e:
        raise _value_error_to_http(e)


@router.post("/candidates/{candidate_id}/check-duplicate")
def check_candidate_duplicate(
    candidate_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        result = queries.check_duplicate(company_id, candidate_id)
        return {
            "warnings": [
                DuplicateWarning(**w).model_dump()
                for w in result["warnings"]
            ],
        }
    except ValueError as e:
        raise _value_error_to_http(e)


@router.post("/candidates/{candidate_id}/hire")
def hire_candidate(
    candidate_id: str,
    body: HireCandidateBody,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    if not body.hire_date:
        raise HTTPException(
            status_code=400,
            detail="Impossible de finaliser l'embauche : champs obligatoires manquants.",
        )
    try:
        employee = commands.hire_candidate(
            candidate_id,
            company_id,
            body.hire_date,
            site=body.site,
            service_name=body.service,
            job_title=body.job_title,
            contract_type=body.contract_type,
            actor_id=str(current_user.id),
        )
        return {
            "ok": True,
            "employee_id": employee["id"],
            "message": "Salarié créé. Complétez les informations pour finaliser l'intégration paie.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─── INTERVIEWS ────────────────────────────────────────────────────────

@router.get("/interviews", response_model=List[InterviewOut])
def list_interviews(
    candidate_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    is_rh = current_user.has_rh_access_in_company(company_id)
    participant_user_id = None if is_rh else str(current_user.id)
    data = queries.list_interviews(
        company_id,
        candidate_id=candidate_id,
        participant_user_id=participant_user_id,
    )
    return [InterviewOut(**x) for x in data]


@router.post("/interviews", response_model=InterviewOut)
def create_interview(
    body: InterviewCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_rh_access(current_user, company_id)
    try:
        out = commands.create_interview(
            company_id, str(current_user.id), body.model_dump()
        )
        return InterviewOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


@router.patch("/interviews/{interview_id}")
def update_interview(
    interview_id: str,
    body: InterviewUpdate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    is_rh = current_user.has_rh_access_in_company(company_id)
    try:
        commands.update_interview(
            interview_id,
            company_id,
            body.model_dump(),
            is_rh,
        )
        return {"ok": True}
    except ValueError as e:
        raise _value_error_to_http(e)


# ─── NOTES ─────────────────────────────────────────────────────────────

@router.get("/notes", response_model=List[NoteOut])
def list_notes(
    candidate_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_collab_or_rh(current_user, company_id, candidate_id)
    data = queries.list_notes(company_id, candidate_id)
    return [NoteOut(**x) for x in data]


@router.post("/notes", response_model=NoteOut)
def create_note(
    body: NoteCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_collab_or_rh(current_user, company_id, body.candidate_id)
    try:
        out = commands.create_note(
            company_id, str(current_user.id), body.model_dump()
        )
        return NoteOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


# ─── OPINIONS ─────────────────────────────────────────────────────────

@router.get("/opinions", response_model=List[OpinionOut])
def list_opinions(
    candidate_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_collab_or_rh(current_user, company_id, candidate_id)
    data = queries.list_opinions(company_id, candidate_id)
    return [OpinionOut(**x) for x in data]


@router.post("/opinions", response_model=OpinionOut)
def create_opinion(
    body: OpinionCreate,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_collab_or_rh(current_user, company_id, body.candidate_id)
    try:
        out = commands.create_opinion(
            company_id, str(current_user.id), body.model_dump()
        )
        return OpinionOut(**out)
    except ValueError as e:
        raise _value_error_to_http(e)


# ─── TIMELINE ──────────────────────────────────────────────────────────

@router.get("/timeline", response_model=List[TimelineEventOut])
def get_timeline(
    candidate_id: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_module_enabled(current_user)
    _ensure_collab_or_rh(current_user, company_id, candidate_id)
    data = queries.get_timeline(company_id, candidate_id)
    return [TimelineEventOut(**x) for x in data]


# ─── REJECTION REASONS ────────────────────────────────────────────────

@router.get("/rejection-reasons")
def get_rejection_reasons(current_user: User = Depends(get_current_user)):
    _ensure_module_enabled(current_user)
    return {"reasons": queries.get_rejection_reasons()}
