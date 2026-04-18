"""Commandes objectifs & KPI."""

from __future__ import annotations

from typing import Any, Dict, List

from app.modules.objectives.application import queries
from app.modules.objectives.infrastructure.repository import objectives_repository
from app.modules.objectives.schemas.requests import (
    CheckinCreate,
    MilestoneCreate,
    MilestoneUpdate,
    ObjectiveCreate,
    ObjectiveEvaluate,
    ObjectiveUpdate,
)
from app.modules.objectives.schemas.responses import DeclineToTeamResult, EmployeeObjective


def create_company_service(company_id: str, name: str) -> Dict[str, Any]:
    if not name or not name.strip():
        raise ValueError("Le nom du service est requis.")
    return objectives_repository.create_service(company_id, name.strip())


def create_objective(
    company_id: str, data: ObjectiveCreate, created_by: str
) -> EmployeeObjective:
    if data.employee_id and data.weight is not None:
        tw = objectives_repository.get_total_weight(
            company_id, data.employee_id, data.period_year, None
        )
        if tw + float(data.weight) > 100.0001:
            raise ValueError(
                "La somme des pondérations dépasse 100%. Ajustez les pondérations existantes."
            )

    milestones_payload: List[Dict[str, Any]] = [
        m.model_dump(mode="json") for m in data.milestones
    ]
    base = data.model_dump(exclude={"milestones"}, mode="json")
    row = objectives_repository.create(
        company_id, {**base, "_milestones": milestones_payload}, created_by
    )
    return queries.employee_objective_from_row(row)


def update_objective(
    objective_id: str, company_id: str, data: ObjectiveUpdate, modified_by: str
) -> EmployeeObjective:
    existing = objectives_repository.get_by_id(objective_id, company_id)
    if not existing:
        raise LookupError("Objectif non trouvé.")

    patch = data.model_dump(exclude_unset=True, mode="json")
    emp_id = patch.get("employee_id", existing.get("employee_id"))
    period = patch.get("period_year", existing.get("period_year"))
    new_weight = patch.get("weight", existing.get("weight"))

    if emp_id and new_weight is not None and period is not None:
        tw = objectives_repository.get_total_weight(
            company_id, str(emp_id), int(period), exclude_objective_id=objective_id
        )
        if tw + float(new_weight) > 100.0001:
            raise ValueError(
                "La somme des pondérations dépasse 100%. Ajustez les pondérations existantes."
            )

    row = objectives_repository.update(objective_id, company_id, patch, modified_by)
    return queries.employee_objective_from_row(row)


def cancel_objective(objective_id: str, company_id: str) -> None:
    objectives_repository.cancel(objective_id, company_id)


def evaluate_objective(
    objective_id: str, company_id: str, data: ObjectiveEvaluate
) -> EmployeeObjective:
    payload = data.model_dump(mode="json", exclude_unset=True)
    row = objectives_repository.evaluate(objective_id, company_id, payload)
    return queries.employee_objective_from_row(row)


def decline_to_team(parent_objective_id: str, company_id: str, created_by: str) -> DeclineToTeamResult:
    parent = objectives_repository.get_by_id(parent_objective_id, company_id)
    if not parent:
        raise LookupError("Objectif parent non trouvé.")
    sid = parent.get("service_id")
    if not sid:
        raise ValueError("L’objectif parent doit être lié à un service.")
    emp_ids = objectives_repository.get_active_employee_ids_for_service(company_id, str(sid))
    if not emp_ids:
        raise ValueError("Aucun collaborateur actif n’est rattaché à ce service.")
    n = objectives_repository.decline_to_team(
        parent_objective_id, company_id, emp_ids, created_by
    )
    return DeclineToTeamResult(created_count=n)


def add_milestone(
    objective_id: str, company_id: str, data: MilestoneCreate, updated_by: str
) -> Dict[str, Any]:
    payload = data.model_dump(mode="json")
    return objectives_repository.add_milestone(objective_id, company_id, payload, updated_by)


def update_milestone(
    objective_id: str,
    milestone_id: str,
    company_id: str,
    data: MilestoneUpdate,
    updated_by: str,
) -> Dict[str, Any]:
    payload = data.model_dump(exclude_unset=True, mode="json")
    return objectives_repository.update_milestone(
        objective_id, milestone_id, company_id, payload, updated_by
    )


def delete_milestone(objective_id: str, milestone_id: str, company_id: str) -> None:
    objectives_repository.delete_milestone(objective_id, milestone_id, company_id)


def add_checkin(
    objective_id: str, company_id: str, data: CheckinCreate, updated_by: str
) -> Dict[str, Any]:
    payload = data.model_dump(mode="json")
    return objectives_repository.add_checkin(objective_id, company_id, payload, updated_by)
