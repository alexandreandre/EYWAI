"""
Mappers DB -> schémas annual_reviews.

Aligné sur api/routers/annual_reviews._row_to_read et construction liste (legacy).
"""

from typing import Any, Dict

from app.modules.annual_reviews.schemas.responses import (
    AnnualReviewListItem,
    AnnualReviewRead,
)


def row_to_annual_review_read(row: Dict[str, Any]) -> AnnualReviewRead:
    """Convertit une ligne DB (annual_reviews) en AnnualReviewRead."""
    return AnnualReviewRead(
        id=row["id"],
        employee_id=row["employee_id"],
        company_id=row["company_id"],
        year=row["year"],
        status=row["status"],
        planned_date=row.get("planned_date"),
        completed_date=row.get("completed_date"),
        employee_preparation_notes=row.get("employee_preparation_notes"),
        employee_preparation_validated_at=row.get("employee_preparation_validated_at"),
        rh_preparation_template=row.get("rh_preparation_template"),
        employee_acceptance_status=row.get("employee_acceptance_status"),
        employee_acceptance_date=row.get("employee_acceptance_date"),
        meeting_report=row.get("meeting_report"),
        rh_notes=row.get("rh_notes"),
        evaluation_summary=row.get("evaluation_summary"),
        objectives_achieved=row.get("objectives_achieved"),
        objectives_next_year=row.get("objectives_next_year"),
        strengths=row.get("strengths"),
        improvement_areas=row.get("improvement_areas"),
        training_needs=row.get("training_needs"),
        career_development=row.get("career_development"),
        salary_review=row.get("salary_review"),
        overall_rating=row.get("overall_rating"),
        next_review_date=row.get("next_review_date"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def row_to_list_item(row: Dict[str, Any]) -> AnnualReviewListItem:
    """Convertit une ligne (avec jointure employees) en AnnualReviewListItem."""
    emp = row.get("employees") or {}
    if isinstance(emp, dict):
        first_name = emp.get("first_name", "")
        last_name = emp.get("last_name", "")
        job_title = emp.get("job_title")
    else:
        first_name = last_name = ""
        job_title = None
    return AnnualReviewListItem(
        id=row["id"],
        employee_id=row["employee_id"],
        first_name=first_name,
        last_name=last_name,
        job_title=job_title,
        year=row["year"],
        status=row["status"],
        planned_date=row.get("planned_date"),
        completed_date=row.get("completed_date"),
        created_at=row.get("created_at"),
    )
