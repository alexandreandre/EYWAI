"""Routes REST compétences (référentiel, évaluations, matrice, export)."""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.database import supabase
from app.core.security import get_current_user
from app.modules.competencies.application import commands, queries
from app.modules.competencies.application.ai_service import talent_ai_service
from app.modules.competencies.schemas.requests import (
    CompetencyRefCreate,
    CompetencyRefUpdate,
    EmployeeCompetencyCreate,
)
from app.modules.competencies.schemas.responses import (
    CompetencyMatrix,
    CompetencyRef,
    EmployeeCompetency,
    MobilityAnalysis,
    MobilityRecommendedPosition,
    MobilityRecommendedTraining,
)
from app.modules.training.infrastructure.repository import training_repository
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/competencies", tags=["Competencies"])


def _handle_application_errors(e: Exception) -> None:
    traceback.print_exc()
    if isinstance(e, PermissionError):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    if isinstance(e, LookupError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    if isinstance(e, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if isinstance(e, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"Erreur inattendue: {str(e)}",
    )


def _company_id(user: User) -> str:
    if not user.active_company_id:
        raise HTTPException(
            status_code=400, detail="Aucune entreprise active sélectionnée."
        )
    return user.active_company_id


def _is_rh(user: User) -> bool:
    if getattr(user, "is_super_admin", False):
        return True
    if not user.active_company_id:
        return False
    return user.has_rh_access_in_company(user.active_company_id)


def _employee_scope_id(user: User, company_id: str) -> Optional[str]:
    return queries.get_employee_id_for_user_scope(str(user.id), company_id)


# --- Référentiel ---


@router.get("/refs", response_model=List[CompetencyRef])
def route_list_refs(
    include_archived: bool = Query(False),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_competency_refs(_company_id(current_user), include_archived)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/refs/{ref_id}", response_model=CompetencyRef)
def route_get_ref(ref_id: str, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        out = queries.get_competency_ref(ref_id, _company_id(current_user))
        if out is None:
            raise HTTPException(status_code=404, detail="Compétence non trouvée.")
        return out
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/refs", response_model=CompetencyRef, status_code=201)
def route_create_ref(
    data: CompetencyRefCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.create_competency_ref(_company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.put("/refs/{ref_id}", response_model=CompetencyRef)
def route_update_ref(
    ref_id: str,
    data: CompetencyRefUpdate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.update_competency_ref(ref_id, _company_id(current_user), data)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.post("/refs/{ref_id}/archive", status_code=204)
def route_archive_ref(ref_id: str, current_user: User = Depends(get_current_user)):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        commands.archive_competency_ref(ref_id, _company_id(current_user))
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


# --- Évaluations ---


@router.get("/evaluations", response_model=List[EmployeeCompetency])
def route_list_evaluations(
    employee_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    cid = _company_id(current_user)
    if _is_rh(current_user):
        try:
            return queries.get_latest_evaluations(cid, employee_id=employee_id)
        except HTTPException:
            raise
        except Exception as e:
            _handle_application_errors(e)
    scope = _employee_scope_id(current_user, cid)
    if not scope:
        raise HTTPException(status_code=403, detail="Profil collaborateur introuvable.")
    if employee_id and employee_id != scope:
        raise HTTPException(status_code=403, detail="Accès non autorisé.")
    try:
        return queries.get_latest_evaluations(cid, employee_id=scope)
    except Exception as e:
        _handle_application_errors(e)


@router.post("/evaluations", response_model=EmployeeCompetency, status_code=201)
def route_evaluate(
    data: EmployeeCompetencyCreate,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return commands.evaluate_employee(
            _company_id(current_user), data, str(current_user.id)
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


# --- Matrice ---


@router.get("/matrix/export")
def route_export_matrix(
    service_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        content, fname = commands.export_matrix_excel_bytes(
            _company_id(current_user), service_id=service_id, category=category
        )
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{fname}"',
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


@router.get("/matrix", response_model=CompetencyMatrix)
def route_matrix(
    service_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    try:
        return queries.get_matrix(
            _company_id(current_user), service_id=service_id, category=category
        )
    except HTTPException:
        raise
    except Exception as e:
        _handle_application_errors(e)


# --- Mobilité IA ---


def _mobility_training_dict(m: dict) -> dict:
    d = dict(m)
    tid = d.get("training_id")
    if tid in (None, "", "null"):
        d["training_id"] = None
    else:
        d["training_id"] = str(tid)
    return d


@router.post(
    "/employees/{employee_id}/analyze-mobility",
    response_model=MobilityAnalysis,
)
def route_analyze_mobility(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    cid = _company_id(current_user)
    try:
        r = (
            supabase.table("employees")
            .select("id, company_id, first_name, last_name, job_title, employment_status")
            .eq("id", employee_id)
            .eq("company_id", cid)
            .maybe_single()
            .execute()
        )
        if not r or not r.data:
            raise HTTPException(status_code=404, detail="Collaborateur introuvable.")
        emp_row = dict(r.data)

        evals = queries.get_latest_evaluations(cid, employee_id)
        competencies = [
            {"name": e.competency_name or e.competency_id, "score": e.score} for e in evals
        ]

        matrix = queries.get_matrix(cid, service_id=None, category=None)
        gaps_cells = [g for g in matrix.gaps if str(g.employee_id) == str(employee_id)]
        gaps = [
            {
                "competency_name": g.competency_name,
                "current_score": g.score,
                "score": g.score,
                "required_level": int(g.required_level) if g.required_level is not None else 0,
            }
            for g in gaps_cells
        ]

        train_rows = training_repository.get_all_trainings(cid, include_archived=False)

        jr = (
            supabase.table("employees")
            .select("job_title")
            .eq("company_id", cid)
            .eq("employment_status", "actif")
            .limit(200)
            .execute()
        )
        titles: List[str] = []
        for row in list(jr.data or []):
            jt = (row.get("job_title") or "").strip()
            if jt and jt not in titles:
                titles.append(jt)
            if len(titles) >= 20:
                break

        employee_payload = {
            "first_name": emp_row.get("first_name"),
            "last_name": emp_row.get("last_name"),
            "job_title": emp_row.get("job_title"),
        }

        raw = talent_ai_service.analyze_mobility(
            employee_payload,
            competencies,
            gaps,
            train_rows,
            titles,
        )

        analyzed_at = datetime.now(timezone.utc)
        posts = [MobilityRecommendedPosition(**x) for x in raw.get("postes_recommandes") or []]
        trains = [
            MobilityRecommendedTraining(**_mobility_training_dict(x))
            for x in raw.get("formations_recommandees") or []
        ]

        return MobilityAnalysis(
            employee_id=str(employee_id),
            mobilite_score=int(raw.get("mobilite_score", 0)),
            potentiel_evolution=str(raw.get("potentiel_evolution") or "Moyen"),
            postes_recommandes=posts,
            formations_recommandees=trains,
            synthese=str(raw.get("synthese") or ""),
            analyzed_at=analyzed_at,
        )
    except HTTPException:
        raise
    except ValueError as e:
        if "OPENAI_API_KEY" in str(e):
            raise HTTPException(
                status_code=503,
                detail="Clé API OpenAI non configurée (OPENAI_API_KEY).",
            )
        raise HTTPException(status_code=400, detail=str(e))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analyse IA : réponse JSON invalide ({e}).",
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/employees/{employee_id}/mobility-analysis")
def route_get_mobility_analysis(
    employee_id: str,
    current_user: User = Depends(get_current_user),
):
    if not _is_rh(current_user):
        raise HTTPException(status_code=403, detail="Accès réservé aux RH.")
    _company_id(current_user)
    _ = employee_id
    raise HTTPException(
        status_code=404,
        detail="Aucune analyse disponible — lancez une analyse",
    )
