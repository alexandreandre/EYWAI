"""Routes API onboarding."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import supabase
from app.core.security import get_current_user
from app.modules.documents.application.queries import get_employee_id_for_user_scope
from app.modules.onboarding.infrastructure.repository import onboarding_repository
from app.modules.onboarding.schemas.responses import OnboardingChecklistOut
from app.modules.users.schemas.responses import User

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


def _company_id(current_user: User) -> Optional[str]:
    return getattr(current_user, "active_company_id", None) or (
        current_user.accessible_companies[0].company_id
        if current_user.accessible_companies
        else None
    )


def _ensure_company(current_user: User) -> str:
    cid = _company_id(current_user)
    if not cid:
        raise HTTPException(status_code=400, detail="Aucune entreprise active")
    return str(cid)


def _employee_in_company(employee_id: str, company_id: str) -> bool:
    res = (
        supabase.table("employees")
        .select("id")
        .eq("id", employee_id)
        .eq("company_id", company_id)
        .maybe_single()
        .execute()
    )
    return bool(res.data)


def _ensure_onboarding_view(
    current_user: User, company_id: str, employee_id: str
) -> None:
    if not _employee_in_company(employee_id, company_id):
        raise HTTPException(status_code=404, detail="Salarié non trouvé")
    if current_user.has_rh_access_in_company(company_id):
        return
    scoped = get_employee_id_for_user_scope(str(current_user.id), company_id)
    if scoped and str(scoped) == str(employee_id):
        return
    raise HTTPException(
        status_code=403,
        detail="Vous n'avez pas accès à cette checklist d'onboarding.",
    )


def _ensure_rh_only(current_user: User, company_id: str) -> None:
    if not current_user.has_rh_access_in_company(company_id):
        raise HTTPException(
            status_code=403,
            detail="Seuls les utilisateurs RH peuvent modifier les tâches d'onboarding.",
        )


@router.get("/me", response_model=OnboardingChecklistOut)
def get_my_onboarding(current_user: User = Depends(get_current_user)):
    """Checklist onboarding du collaborateur connecté (résolution profil employé)."""
    company_id = _ensure_company(current_user)
    eid = get_employee_id_for_user_scope(str(current_user.id), company_id)
    if not eid:
        raise HTTPException(
            status_code=404,
            detail="Aucun profil collaborateur lié à votre compte pour cette entreprise.",
        )
    data = onboarding_repository.get_checklist_by_employee(str(eid), company_id)
    if not data:
        data = onboarding_repository.create_checklist(str(eid), company_id)
    return OnboardingChecklistOut(**data)


@router.get("/{employee_id}", response_model=OnboardingChecklistOut)
def get_onboarding(employee_id: str, current_user: User = Depends(get_current_user)):
    company_id = _ensure_company(current_user)
    _ensure_onboarding_view(current_user, company_id, employee_id)
    data = onboarding_repository.get_checklist_by_employee(employee_id, company_id)
    if not data:
        data = onboarding_repository.create_checklist(employee_id, company_id)
    return OnboardingChecklistOut(**data)


@router.post("/{employee_id}/tasks/{task_id}/complete")
def complete_onboarding_task(
    employee_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_company(current_user)
    _ensure_rh_only(current_user, company_id)
    _ensure_onboarding_view(current_user, company_id, employee_id)
    cl = onboarding_repository.get_checklist_by_employee(employee_id, company_id)
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist introuvable.")
    checklist_id = str(cl["id"])
    if not any(str(t["id"]) == str(task_id) for t in cl.get("tasks", [])):
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    ok = onboarding_repository.complete_task(
        task_id, checklist_id, company_id, str(current_user.id)
    )
    if not ok:
        raise HTTPException(status_code=400, detail="Impossible de compléter la tâche.")
    return {"success": True}


@router.post("/{employee_id}/tasks/{task_id}/uncomplete")
def uncomplete_onboarding_task(
    employee_id: str,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    company_id = _ensure_company(current_user)
    _ensure_rh_only(current_user, company_id)
    _ensure_onboarding_view(current_user, company_id, employee_id)
    cl = onboarding_repository.get_checklist_by_employee(employee_id, company_id)
    if not cl:
        raise HTTPException(status_code=404, detail="Checklist introuvable.")
    checklist_id = str(cl["id"])
    if not any(str(t["id"]) == str(task_id) for t in cl.get("tasks", [])):
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    ok = onboarding_repository.uncomplete_task(task_id, checklist_id, company_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Impossible de réinitialiser la tâche.")
    return {"success": True}
