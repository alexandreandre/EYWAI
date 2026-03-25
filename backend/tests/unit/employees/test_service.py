"""
Tests unitaires du service applicatif employees (enrichissements).

Enrichissement titre de séjour et entretien annuel avec dépendances mockées.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application.service import (
    enrich_employee_with_annual_review,
    enrich_employee_with_residence_permit_status,
)


pytestmark = pytest.mark.unit


@patch("app.modules.employees.application.service.get_residence_permit_calculator")
def test_enrich_employee_with_residence_permit_status_adds_calculated_fields(
    mock_get_calculator,
):
    """enrich_employee_with_residence_permit_status : ajoute statut et jours restants."""
    calculator = MagicMock()
    calculator.calculate.return_value = {
        "residence_permit_status": "valid",
        "residence_permit_days_remaining": 90,
        "residence_permit_data_complete": True,
    }
    mock_get_calculator.return_value = calculator
    employee_data = {
        "id": "e1",
        "first_name": "Jean",
        "is_subject_to_residence_permit": True,
        "residence_permit_expiry_date": "2025-06-30",
        "employment_status": "actif",
    }
    result = enrich_employee_with_residence_permit_status(employee_data)
    assert result["residence_permit_status"] == "valid"
    assert result["residence_permit_days_remaining"] == 90
    assert result["residence_permit_data_complete"] is True
    calculator.calculate.assert_called_once()
    call_kw = calculator.calculate.call_args[1]
    assert call_kw["is_subject_to_residence_permit"] is True
    assert call_kw["employment_status"] == "actif"


@patch("app.modules.employees.application.service.get_residence_permit_calculator")
def test_enrich_employee_with_residence_permit_status_uses_default_employment_status(
    mock_get_calculator,
):
    """Sans employment_status, utilise DEFAULT_EMPLOYMENT_STATUS (actif)."""
    calculator = MagicMock()
    calculator.calculate.return_value = {
        "residence_permit_status": "to_renew",
        "residence_permit_days_remaining": 30,
        "residence_permit_data_complete": True,
    }
    mock_get_calculator.return_value = calculator
    employee_data = {
        "id": "e1",
        "is_subject_to_residence_permit": False,
        "residence_permit_expiry_date": None,
    }
    enrich_employee_with_residence_permit_status(employee_data)
    call_kw = calculator.calculate.call_args[1]
    assert call_kw["employment_status"] == "actif"


@patch("app.modules.employees.application.service.get_residence_permit_calculator")
def test_enrich_employee_with_residence_permit_status_on_exception_returns_unchanged(
    mock_get_calculator,
):
    """Si le calculateur lève une exception, retourne les données inchangées."""
    calculator = MagicMock()
    calculator.calculate.side_effect = ValueError("Invalid date")
    mock_get_calculator.return_value = calculator
    employee_data = {"id": "e1", "first_name": "Jean"}
    result = enrich_employee_with_residence_permit_status(employee_data)
    assert result == employee_data


@patch("app.modules.employees.application.service.get_annual_review_query")
def test_enrich_employee_with_annual_review_adds_review_fields(mock_get_query):
    """enrich_employee_with_annual_review : ajoute statut et dates entretien courants."""
    query = MagicMock()
    query.fetch_for_employee_year.return_value = {
        "status": "planned",
        "planned_date": "2025-03-15",
        "completed_date": None,
    }
    mock_get_query.return_value = query
    employee_data = {"id": "e1", "company_id": "c1", "first_name": "Jean"}
    result = enrich_employee_with_annual_review(employee_data)
    assert result["annual_review_current_status"] == "planned"
    assert result["annual_review_current_year"] == date.today().year
    assert result["annual_review_current_planned_date"] == "2025-03-15"
    assert result["annual_review_current_completed_date"] is None
    query.fetch_for_employee_year.assert_called_once()
    args = query.fetch_for_employee_year.call_args[0]
    assert args[0] == "e1"
    assert args[1] == "c1"
    assert args[2] == date.today().year


@patch("app.modules.employees.application.service.get_annual_review_query")
def test_enrich_employee_with_annual_review_no_review_sets_none(mock_get_query):
    """Sans entretien pour l'année courante, champs annuels à None."""
    query = MagicMock()
    query.fetch_for_employee_year.return_value = None
    mock_get_query.return_value = query
    employee_data = {"id": "e1", "company_id": "c1"}
    result = enrich_employee_with_annual_review(employee_data)
    assert result["annual_review_current_status"] is None
    assert result["annual_review_current_year"] is None
    assert result["annual_review_current_planned_date"] is None
    assert result["annual_review_current_completed_date"] is None


@patch("app.modules.employees.application.service.get_annual_review_query")
def test_enrich_employee_with_annual_review_missing_id_or_company_returns_unchanged(
    mock_get_query,
):
    """Sans id ou company_id, retourne les données inchangées."""
    employee_data = {"first_name": "Jean"}  # pas d'id ni company_id
    result = enrich_employee_with_annual_review(employee_data)
    assert result == employee_data
    mock_get_query.assert_not_called()
