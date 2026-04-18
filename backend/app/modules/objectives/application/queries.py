"""Lecture objectifs & KPI."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.modules.objectives.infrastructure.repository import objectives_repository
from app.modules.objectives.schemas.responses import (
    CompanyService,
    EmployeeObjective,
    ObjectiveCheckin,
    ObjectiveMilestone,
)


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def _parse_date_required(val: Any) -> date:
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def _milestone_from_row(row: Dict[str, Any]) -> ObjectiveMilestone:
    return ObjectiveMilestone(
        id=str(row["id"]),
        objective_id=str(row["objective_id"]),
        milestone_date=_parse_date_required(row.get("milestone_date")),
        expected_value=float(row.get("expected_value") or 0),
        actual_value=float(row["actual_value"]) if row.get("actual_value") is not None else None,
        comment=row.get("comment"),
        updated_by=str(row["updated_by"]) if row.get("updated_by") else None,
        updated_at=_parse_dt(row.get("updated_at")),
    )


def _checkin_from_row(row: Dict[str, Any]) -> ObjectiveCheckin:
    return ObjectiveCheckin(
        id=str(row["id"]),
        objective_id=str(row["objective_id"]),
        checkin_date=_parse_date_required(row.get("checkin_date")),
        progress_note=str(row.get("progress_note") or ""),
        updated_by=str(row["updated_by"]) if row.get("updated_by") else None,
        updated_at=_parse_dt(row.get("updated_at")),
    )


def employee_objective_from_row(row: Dict[str, Any]) -> EmployeeObjective:
    r = dict(row)
    ms_raw = r.pop("_milestones", [])
    ck_raw = r.pop("_checkins", [])
    employee_name = r.pop("_employee_name", None)
    service_name = r.pop("_service_name", None)

    milestones = [_milestone_from_row(dict(x)) for x in ms_raw]
    checkins = [_checkin_from_row(dict(x)) for x in ck_raw]

    def pd(key: str) -> Optional[date]:
        v = r.get(key)
        if v is None:
            return None
        if isinstance(v, date) and not isinstance(v, datetime):
            return v
        if isinstance(v, datetime):
            return v.date()
        return date.fromisoformat(str(v)[:10])

    return EmployeeObjective(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        employee_id=str(r["employee_id"]) if r.get("employee_id") else None,
        service_id=str(r["service_id"]) if r.get("service_id") else None,
        parent_objective_id=str(r["parent_objective_id"]) if r.get("parent_objective_id") else None,
        title=str(r.get("title") or ""),
        type=str(r.get("type") or "qualitative"),
        period_year=int(r.get("period_year") or 0),
        status=str(r.get("status") or "draft"),
        description=r.get("description"),
        kpi_label=r.get("kpi_label"),
        kpi_unit=r.get("kpi_unit"),
        kpi_target_value=float(r["kpi_target_value"]) if r.get("kpi_target_value") is not None else None,
        kpi_initial_value=float(r["kpi_initial_value"]) if r.get("kpi_initial_value") is not None else None,
        due_date=pd("due_date"),
        weight=float(r["weight"]) if r.get("weight") is not None else None,
        annual_review_id=str(r["annual_review_id"]) if r.get("annual_review_id") else None,
        notes=r.get("notes"),
        evaluation_date=pd("evaluation_date"),
        final_achievement_rate=float(r["final_achievement_rate"])
        if r.get("final_achievement_rate") is not None
        else None,
        evaluation_comment=r.get("evaluation_comment"),
        evaluated_in_review_id=str(r["evaluated_in_review_id"])
        if r.get("evaluated_in_review_id")
        else None,
        last_modified_by=str(r["last_modified_by"]) if r.get("last_modified_by") else None,
        created_by=str(r["created_by"]) if r.get("created_by") else None,
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
        milestones=milestones,
        checkins=checkins,
        employee_name=employee_name,
        service_name=service_name,
    )


def list_company_services(company_id: str) -> List[CompanyService]:
    rows = objectives_repository.list_services(company_id)
    return [CompanyService.model_validate(dict(x)) for x in rows]


def get_objectives(
    company_id: str,
    employee_id: Optional[str] = None,
    service_id: Optional[str] = None,
    period_year: Optional[int] = None,
    status: Optional[str] = None,
    include_inactive_employees: bool = False,
) -> List[EmployeeObjective]:
    rows = objectives_repository.get_all(
        company_id,
        employee_id=employee_id,
        service_id=service_id,
        period_year=period_year,
        status=status,
        include_inactive_employees=include_inactive_employees,
    )
    return [employee_objective_from_row(dict(x)) for x in rows]


def get_objective(objective_id: str, company_id: str) -> Optional[EmployeeObjective]:
    row = objectives_repository.get_by_id(objective_id, company_id)
    if not row:
        return None
    return employee_objective_from_row(dict(row))


def get_previous_year_objectives_for_objective(
    objective_id: str, company_id: str
) -> List[EmployeeObjective]:
    cur = objectives_repository.get_by_id(objective_id, company_id)
    if not cur:
        raise LookupError("Objectif non trouvé.")
    eid = cur.get("employee_id")
    if not eid:
        return []
    py = int(cur.get("period_year") or 0)
    rows = objectives_repository.get_previous_year_rows(company_id, str(eid), py)
    return [employee_objective_from_row(dict(x)) for x in rows]


def get_achievement_rate(company_id: str, period_year: int) -> Optional[float]:
    return objectives_repository.get_achievement_rate(company_id, period_year)


def objective_milestone_from_row(row: Dict[str, Any]) -> ObjectiveMilestone:
    return _milestone_from_row(row)


def objective_checkin_from_row(row: Dict[str, Any]) -> ObjectiveCheckin:
    return _checkin_from_row(row)


def get_employee_id_for_user_scope(user_id: str, company_id: str) -> Optional[str]:
    """Résout l'employé courant (user + entreprise) pour le périmètre salarié."""
    return objectives_repository.get_employee_id_for_user(user_id, company_id)
