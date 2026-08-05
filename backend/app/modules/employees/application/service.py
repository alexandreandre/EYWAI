"""
Orchestration partagée du module employees.

Enrichissements (titre de séjour, entretien annuel) via domain rules et infrastructure.
Aucun accès direct à la DB : utilise les ports (calculateur résidence, query entretien annuel).
"""

from __future__ import annotations
from app.core.logging import get_logger

logger = get_logger("modules.employees.application.service")

from datetime import date
from typing import Any, Dict

from app.modules.employees.domain.rules import DEFAULT_EMPLOYMENT_STATUS
from app.modules.employees.domain.trial_period import calculate_trial_period_status
from app.modules.employees.infrastructure.providers import (
    get_residence_permit_calculator,
)
from app.modules.employees.infrastructure.queries import (
    fetch_exit_summary_for_employee,
    get_annual_review_query,
)


def enrich_employee_with_residence_permit_status(
    employee_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrichit les données d'un employé avec le statut calculé du titre de séjour.
    Comportement identique au router legacy. Utilise IResidencePermitStatusCalculator.
    """
    try:
        is_subject = employee_data.get("is_subject_to_residence_permit", False)
        expiry_date_str = employee_data.get("residence_permit_expiry_date")
        employment_status = employee_data.get(
            "employment_status", DEFAULT_EMPLOYMENT_STATUS
        )

        expiry_date = None
        if expiry_date_str:
            if isinstance(expiry_date_str, str):
                expiry_date = date.fromisoformat(expiry_date_str)
            elif isinstance(expiry_date_str, date):
                expiry_date = expiry_date_str

        calculator = get_residence_permit_calculator()
        status_data = calculator.calculate(
            is_subject_to_residence_permit=is_subject,
            residence_permit_expiry_date=expiry_date,
            employment_status=employment_status,
        )
        result = dict(employee_data)
        result.update(status_data)
        return result
    except Exception:
        logger.exception("Exception")
        return employee_data


def enrich_employee_with_trial_period_status(
    employee_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Enrichit la fiche avec le statut calculé de la période d'essai."""
    try:
        hire_date_str = employee_data.get("hire_date")
        hire_date = None
        if hire_date_str:
            if isinstance(hire_date_str, str):
                hire_date = date.fromisoformat(hire_date_str[:10])
            elif isinstance(hire_date_str, date):
                hire_date = hire_date_str

        status_data = calculate_trial_period_status(
            hire_date,
            employee_data.get("trial_period"),
            employee_data.get("employment_status", DEFAULT_EMPLOYMENT_STATUS),
        )
        result = dict(employee_data)
        result.update(status_data)
        return result
    except Exception:
        logger.exception("Exception")
        return employee_data


def enrich_employee_with_annual_review(
    employee_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrichit les données d'un employé avec l'entretien annuel de l'année courante.
    Comportement identique au router legacy. Utilise IAnnualReviewQuery.
    """
    try:
        employee_id = employee_data.get("id")
        company_id = employee_data.get("company_id")
        if not employee_id or not company_id:
            return employee_data

        current_year = date.today().year
        query = get_annual_review_query()
        review = query.fetch_for_employee_year(employee_id, company_id, current_year)
        result = dict(employee_data)
        if review:
            result["annual_review_current_status"] = review.get("status")
            result["annual_review_current_year"] = current_year
            result["annual_review_current_planned_date"] = review.get("planned_date")
            result["annual_review_current_completed_date"] = review.get(
                "completed_date"
            )
        else:
            result["annual_review_current_status"] = None
            result["annual_review_current_year"] = None
            result["annual_review_current_planned_date"] = None
            result["annual_review_current_completed_date"] = None
        return result
    except Exception as e:
        logger.warning(f'ERROR [enrich_employee_with_annual_review]: {e}')
        logger.exception("Exception")
        return employee_data


def enrich_employee_with_exit_context(
    employee_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Enrichit la fiche avec le contexte de départ (dernier jour travaillé, type, statut).
    Permet au RH de consulter le dossier documents pendant la période de sortie.
    """
    result = dict(employee_data)
    exit_id = employee_data.get("current_exit_id")
    company_id = employee_data.get("company_id")
    if not exit_id or not company_id:
        result["exit_last_working_day"] = None
        result["exit_type"] = None
        result["exit_status"] = None
        return result

    summary = fetch_exit_summary_for_employee(str(exit_id), str(company_id))
    if not summary:
        result["exit_last_working_day"] = None
        result["exit_type"] = None
        result["exit_status"] = None
        return result

    result["current_exit_id"] = str(summary.get("id") or exit_id)
    result["exit_last_working_day"] = summary.get("last_working_day")
    result["exit_type"] = summary.get("exit_type")
    result["exit_status"] = summary.get("status")
    return result
