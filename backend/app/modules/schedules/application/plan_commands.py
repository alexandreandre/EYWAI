"""
Cas d'usage RH pour les plans de calendriers horaires et la génération.

Valide l'accès RH sur l'entreprise active puis délègue au repository / service.
Lève ScheduleAppError (converti en HTTPException par le router).
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.modules.schedules.application import calendar_generation
from app.modules.schedules.application.exceptions import ScheduleAppError
from app.modules.schedules.application.preset_apply import apply_preset as _apply_preset
from app.modules.schedules.application.presets_2026 import list_presets as _list_presets
from app.modules.schedules.infrastructure import schedule_plans_repository as plans_repo


def _require_company(current_user: Any) -> str:
    company_id = current_user.active_company_id
    if not company_id:
        raise ScheduleAppError("validation", "Aucune entreprise active", status_code=400)
    if not current_user.has_rh_access_in_company(company_id):
        raise ScheduleAppError("forbidden", "Accès réservé aux RH", status_code=403)
    return str(company_id)


def list_plans(current_user: Any) -> List[Dict[str, Any]]:
    company_id = _require_company(current_user)
    return plans_repo.list_plans(company_id)


def create_plan(payload: Any, current_user: Any) -> Dict[str, Any]:
    company_id = _require_company(current_user)
    return plans_repo.create_plan(company_id, payload.model_dump())


def update_plan(plan_id: str, payload: Any, current_user: Any) -> Dict[str, Any]:
    company_id = _require_company(current_user)
    if not plans_repo.get_plan(company_id, plan_id):
        raise ScheduleAppError("not_found", "Plan introuvable", status_code=404)
    return plans_repo.update_plan(company_id, plan_id, payload.model_dump())


def delete_plan(plan_id: str, current_user: Any) -> Dict[str, str]:
    company_id = _require_company(current_user)
    plans_repo.delete_plan(company_id, plan_id)
    return {"status": "success"}


def list_presets(current_user: Any) -> List[Dict[str, Any]]:
    _require_company(current_user)
    return _list_presets()


def apply_preset(preset_key: str, current_user: Any) -> Dict[str, Any]:
    company_id = _require_company(current_user)
    try:
        return _apply_preset(company_id, preset_key)
    except ValueError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e


def generate(payload: Any, current_user: Any) -> Dict[str, Any]:
    company_id = _require_company(current_user)
    # Sans plan_id : génère tous les plans actifs de la société (précédence portée).
    if not payload.plan_id:
        return calendar_generation.generate_all_active_plans(
            company_id,
            year=payload.year,
            dry_run=payload.dry_run,
            recalculate_payroll=payload.recalculate_payroll,
        )
    try:
        return calendar_generation.generate_from_plan(
            company_id,
            payload.plan_id,
            year=payload.year,
            overwrite_mode=payload.overwrite_mode,
            dry_run=payload.dry_run,
            recalculate_payroll=payload.recalculate_payroll,
        )
    except ValueError as e:
        raise ScheduleAppError("validation", str(e), status_code=400) from e


__all__ = [
    "list_plans",
    "create_plan",
    "update_plan",
    "delete_plan",
    "list_presets",
    "apply_preset",
    "generate",
]
