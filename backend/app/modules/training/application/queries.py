"""Lecture catalogue formations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.modules.training.infrastructure.repository import training_repository
from app.modules.training.schemas.responses import (
    TrainingCatalog,
    TrainingEnrollment,
    TrainingEvaluationSummaryItem,
)


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    return date.fromisoformat(str(val)[:10])


def _parse_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime.combine(val, datetime.min.time())
    return datetime.fromisoformat(str(val).replace("Z", "+00:00"))


def training_catalog_from_row(row: Dict[str, Any]) -> TrainingCatalog:
    r = dict(row)
    cert_ref = r.pop("_certification_ref", None)
    enrolled = int(r.pop("_enrolled_count", 0) or 0)
    cats = r.get("categories")
    if isinstance(cats, list):
        cat_list = [str(x) for x in cats]
    else:
        from app.modules.training.infrastructure.repository import _categories_from_db

        cat_list = _categories_from_db(cats)
    return TrainingCatalog(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        title=str(r.get("title") or ""),
        training_type=str(r.get("training_type") or ""),
        provider=r.get("provider"),
        duration_hours=float(r["duration_hours"]) if r.get("duration_hours") is not None else None,
        unit_cost_ht=float(r["unit_cost_ht"]) if r.get("unit_cost_ht") is not None else None,
        pedagogical_objective=r.get("pedagogical_objective"),
        categories=cat_list,
        certification_id=str(r["certification_id"]) if r.get("certification_id") else None,
        competency_id=str(r["competency_id"]) if r.get("competency_id") else None,
        status=str(r.get("status") or "active"),
        program_url=r.get("program_url"),
        external_link=r.get("external_link"),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
        certification_ref=cert_ref,
        enrolled_count=enrolled,
    )


def training_enrollment_from_row(
    row: Dict[str, Any],
    suggest: bool = False,
    suggested_certification_id: Optional[str] = None,
) -> TrainingEnrollment:
    emp_name = row.get("_employee_name")
    ttitle = row.get("_training_title")
    ucost = row.get("_unit_cost_ht")
    r = dict(row)
    r.pop("_employee_name", None)
    r.pop("_training_title", None)
    r.pop("_unit_cost_ht", None)
    mgr_display = r.pop("_manager_display_name", None)
    return TrainingEnrollment(
        id=str(r["id"]),
        company_id=str(r["company_id"]),
        training_id=str(r["training_id"]),
        employee_id=str(r["employee_id"]),
        status=str(r.get("status") or "planned"),
        planned_date=_parse_date(r.get("planned_date")),
        completion_date=_parse_date(r.get("completion_date")),
        notes=r.get("notes"),
        created_at=_parse_dt(r.get("created_at")),
        updated_at=_parse_dt(r.get("updated_at")),
        employee_name=emp_name,
        training_title=ttitle,
        unit_cost_ht=float(ucost) if ucost is not None else None,
        suggest_certification_creation=suggest,
        suggested_certification_id=suggested_certification_id,
        requested_by=str(r["requested_by"]) if r.get("requested_by") else None,
        manager_id=str(r["manager_id"]) if r.get("manager_id") else None,
        manager_approved_at=_parse_dt(r.get("manager_approved_at")),
        manager_rejected_at=_parse_dt(r.get("manager_rejected_at")),
        manager_rejection_reason=r.get("manager_rejection_reason"),
        rh_approved_at=_parse_dt(r.get("rh_approved_at")),
        rh_rejected_at=_parse_dt(r.get("rh_rejected_at")),
        rh_rejection_reason=r.get("rh_rejection_reason"),
        manager_display_name=mgr_display,
        rating=int(r["rating"]) if r.get("rating") is not None else None,
        evaluation_comment=r.get("evaluation_comment"),
        evaluated_at=_parse_dt(r.get("evaluated_at")),
        certificate_url=r.get("certificate_url"),
        certificate_uploaded_at=_parse_dt(r.get("certificate_uploaded_at")),
    )


def get_evaluations_summary(company_id: str) -> List[TrainingEvaluationSummaryItem]:
    rows = training_repository.get_evaluations_summary(company_id)
    return [TrainingEvaluationSummaryItem(**dict(x)) for x in rows]


def get_trainings(company_id: str, include_archived: bool = False) -> List[TrainingCatalog]:
    rows = training_repository.get_all_trainings(company_id, include_archived=include_archived)
    return [training_catalog_from_row(dict(x)) for x in rows]


def get_training(training_id: str, company_id: str) -> Optional[TrainingCatalog]:
    row = training_repository.get_training_by_id(training_id, company_id)
    if not row:
        return None
    return training_catalog_from_row(dict(row))


def get_enrollments(
    company_id: str,
    training_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[TrainingEnrollment]:
    rows = training_repository.get_enrollments(
        company_id, training_id=training_id, employee_id=employee_id, status=status
    )
    return [training_enrollment_from_row(dict(x)) for x in rows]


def get_enrollment(enrollment_id: str, company_id: str) -> Optional[TrainingEnrollment]:
    row = training_repository.get_enrollment_by_id(enrollment_id, company_id)
    if not row:
        return None
    return training_enrollment_from_row(dict(row))


def get_total_consumed(company_id: str, year: int) -> float:
    return training_repository.get_total_consumed(company_id, year)


def get_employee_id_for_user_scope(user_id: str, company_id: str) -> Optional[str]:
    return training_repository.get_employee_id_for_user(user_id, company_id)
