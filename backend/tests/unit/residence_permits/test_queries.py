"""
Tests unitaires des queries du module residence_permits.

get_residence_permits_list avec repository mocké (pas de DB).
"""
from unittest.mock import MagicMock, patch

import pytest

from app.modules.residence_permits.application.queries import get_residence_permits_list
from app.modules.residence_permits.schemas.responses import ResidencePermitListItem


pytestmark = pytest.mark.unit

COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


class TestGetResidencePermitsList:
    """get_residence_permits_list(company_id)."""

    @patch("app.modules.residence_permits.application.queries.get_residence_permit_status_calculator")
    @patch("app.modules.residence_permits.application.queries._repo")
    def test_returns_list_of_items(
        self, mock_repo: MagicMock, mock_get_calculator: MagicMock
    ):
        """Appelle le repo, enrichit chaque ligne avec le calculateur, retourne des ResidencePermitListItem."""
        mock_repo.get_employees_subject_for_company.return_value = [
            {
                "id": "emp-1",
                "first_name": "Jean",
                "last_name": "Dupont",
                "is_subject_to_residence_permit": True,
                "residence_permit_expiry_date": "2026-06-15",
                "employment_status": "actif",
            },
        ]
        mock_calc = MagicMock()
        mock_calc.calculate_residence_permit_status.return_value = {
            "is_subject_to_residence_permit": True,
            "residence_permit_status": "valid",
            "residence_permit_expiry_date": "2026-06-15",
            "residence_permit_days_remaining": 90,
            "residence_permit_data_complete": True,
        }
        mock_get_calculator.return_value = mock_calc

        result = get_residence_permits_list(COMPANY_ID)

        mock_repo.get_employees_subject_for_company.assert_called_once_with(COMPANY_ID)
        mock_get_calculator.assert_called_once()
        mock_calc.calculate_residence_permit_status.assert_called_once()
        assert len(result) == 1
        assert isinstance(result[0], ResidencePermitListItem)
        assert result[0].employee_id == "emp-1"
        assert result[0].first_name == "Jean"
        assert result[0].last_name == "Dupont"
        assert result[0].residence_permit_status == "valid"
        assert result[0].residence_permit_days_remaining == 90

    @patch("app.modules.residence_permits.application.queries.get_residence_permit_status_calculator")
    @patch("app.modules.residence_permits.application.queries._repo")
    def test_empty_list_when_no_employees(
        self, mock_repo: MagicMock, mock_get_calculator: MagicMock
    ):
        """Si le repo retourne une liste vide, la query retourne une liste vide."""
        mock_repo.get_employees_subject_for_company.return_value = []
        mock_calc = MagicMock()
        mock_get_calculator.return_value = mock_calc

        result = get_residence_permits_list(COMPANY_ID)

        mock_repo.get_employees_subject_for_company.assert_called_once_with(COMPANY_ID)
        mock_calc.calculate_residence_permit_status.assert_not_called()
        assert result == []

    @patch("app.modules.residence_permits.application.queries.get_residence_permit_status_calculator")
    @patch("app.modules.residence_permits.application.queries._repo")
    def test_multiple_rows_enriched_and_mapped(
        self, mock_repo: MagicMock, mock_get_calculator: MagicMock
    ):
        """Plusieurs lignes : chaque ligne est enrichie et mappée en ResidencePermitListItem."""
        mock_repo.get_employees_subject_for_company.return_value = [
            {"id": "e1", "first_name": "A", "last_name": "Alpha", "employment_status": "actif"},
            {"id": "e2", "first_name": "B", "last_name": "Beta", "employment_status": "en_sortie"},
        ]
        mock_calc = MagicMock()
        def side_effect(**kwargs):
            return {
                "is_subject_to_residence_permit": True,
                "residence_permit_status": "to_renew",
                "residence_permit_expiry_date": None,
                "residence_permit_days_remaining": 30,
                "residence_permit_data_complete": True,
            }
        mock_calc.calculate_residence_permit_status.side_effect = side_effect
        mock_get_calculator.return_value = mock_calc

        result = get_residence_permits_list(COMPANY_ID)

        assert len(result) == 2
        assert result[0].employee_id == "e1" and result[0].last_name == "Alpha"
        assert result[1].employee_id == "e2" and result[1].last_name == "Beta"
        assert mock_calc.calculate_residence_permit_status.call_count == 2
