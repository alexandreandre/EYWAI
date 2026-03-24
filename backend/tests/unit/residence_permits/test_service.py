"""
Tests unitaires du service applicatif residence_permits.

enrich_row_with_residence_permit_status et _parse_expiry_date (via enrichissement)
avec calculateur mocké. Pas de DB.
"""
from datetime import date
from unittest.mock import MagicMock

import pytest

from app.modules.residence_permits.application.service import (
    enrich_row_with_residence_permit_status,
    _parse_expiry_date,
)
from app.modules.residence_permits.domain.interfaces import IResidencePermitStatusCalculator


pytestmark = pytest.mark.unit


# --- _parse_expiry_date (testé indirectement via enrich_row ; on peut l'exposer en test si besoin)
# Le module ne l'exporte pas dans __all__ mais il est importable depuis application.service.


class TestParseExpiryDate:
    """_parse_expiry_date : parsing de la date d'expiration depuis une ligne employé."""

    def test_none_returns_none(self):
        assert _parse_expiry_date(None) is None

    def test_date_instance_returned_as_is(self):
        d = date(2026, 6, 15)
        assert _parse_expiry_date(d) == d

    def test_iso_string_parsed(self):
        assert _parse_expiry_date("2026-06-15") == date(2026, 6, 15)

    def test_invalid_string_returns_none(self):
        assert _parse_expiry_date("not-a-date") is None
        assert _parse_expiry_date("") is None

    def test_other_type_returns_none(self):
        assert _parse_expiry_date(12345) is None
        assert _parse_expiry_date([]) is None


class TestEnrichRowWithResidencePermitStatus:
    """enrich_row_with_residence_permit_status : enrichit les données employé avec le statut calculé."""

    def test_calls_calculator_with_expected_args(self):
        employee_data = {
            "id": "emp-1",
            "first_name": "Jean",
            "last_name": "Dupont",
            "is_subject_to_residence_permit": True,
            "residence_permit_expiry_date": "2026-06-15",
            "employment_status": "actif",
        }
        mock_calculator = MagicMock(spec=IResidencePermitStatusCalculator)
        mock_calculator.calculate_residence_permit_status.return_value = {
            "is_subject_to_residence_permit": True,
            "residence_permit_status": "valid",
            "residence_permit_expiry_date": "2026-06-15",
            "residence_permit_days_remaining": 90,
            "residence_permit_data_complete": True,
        }

        result = enrich_row_with_residence_permit_status(employee_data, mock_calculator)

        mock_calculator.calculate_residence_permit_status.assert_called_once()
        call_kw = mock_calculator.calculate_residence_permit_status.call_args[1]
        assert call_kw["is_subject_to_residence_permit"] is True
        assert call_kw["residence_permit_expiry_date"] == date(2026, 6, 15)
        assert call_kw["employment_status"] == "actif"
        assert result["residence_permit_status"] == "valid"
        assert result["residence_permit_days_remaining"] == 90
        assert result["first_name"] == "Jean"
        assert result["last_name"] == "Dupont"

    def test_enrichment_merges_status_into_row(self):
        employee_data = {
            "id": "emp-2",
            "first_name": "Marie",
            "is_subject_to_residence_permit": True,
            "residence_permit_expiry_date": None,
            "employment_status": "actif",
        }
        mock_calculator = MagicMock(spec=IResidencePermitStatusCalculator)
        mock_calculator.calculate_residence_permit_status.return_value = {
            "is_subject_to_residence_permit": True,
            "residence_permit_status": "to_complete",
            "residence_permit_expiry_date": None,
            "residence_permit_days_remaining": None,
            "residence_permit_data_complete": False,
        }

        result = enrich_row_with_residence_permit_status(employee_data, mock_calculator)

        assert result["residence_permit_status"] == "to_complete"
        assert result["residence_permit_data_complete"] is False
        assert result["id"] == "emp-2"
        assert result["first_name"] == "Marie"

    def test_uses_default_employment_status_when_missing(self):
        employee_data = {
            "id": "emp-3",
            "is_subject_to_residence_permit": True,
            "residence_permit_expiry_date": None,
        }
        mock_calculator = MagicMock(spec=IResidencePermitStatusCalculator)
        mock_calculator.calculate_residence_permit_status.return_value = {
            "is_subject_to_residence_permit": True,
            "residence_permit_status": "to_complete",
            "residence_permit_expiry_date": None,
            "residence_permit_days_remaining": None,
            "residence_permit_data_complete": False,
        }

        enrich_row_with_residence_permit_status(employee_data, mock_calculator)

        call_kw = mock_calculator.calculate_residence_permit_status.call_args[1]
        assert call_kw["employment_status"] == "actif"

    def test_reference_date_passed_to_calculator(self):
        employee_data = {
            "id": "emp-4",
            "is_subject_to_residence_permit": True,
            "residence_permit_expiry_date": "2026-12-31",
            "employment_status": "actif",
        }
        ref = date(2025, 6, 1)
        mock_calculator = MagicMock(spec=IResidencePermitStatusCalculator)
        mock_calculator.calculate_residence_permit_status.return_value = {}

        enrich_row_with_residence_permit_status(
            employee_data, mock_calculator, reference_date=ref
        )

        call_kw = mock_calculator.calculate_residence_permit_status.call_args[1]
        assert call_kw["reference_date"] == ref
