"""
Tests unitaires des queries du module payslips (application/queries.py).

Chaque query est testée avec l'infrastructure mockée (pas de DB, pas de HTTP).
"""
from unittest.mock import patch


from app.modules.payslips.application.queries import (
    get_my_payslips,
    get_employee_payslips,
    get_payslip_details,
    get_payslip_history,
)


class TestGetMyPayslipsQuery:
    """Tests de la query get_my_payslips."""

    def test_returns_list_from_infra(self):
        """get_my_payslips retourne la liste renvoyée par l'infrastructure."""
        expected = [
            {"id": "ps-1", "name": "Bulletin_01-2024.pdf", "month": 1, "year": 2024, "url": "https://signed.url/1", "net_a_payer": 2500.0},
        ]
        with patch(
            "app.modules.payslips.application.queries._get_my_payslips",
            return_value=expected,
        ) as mock_infra:
            result = get_my_payslips("emp-1")
        mock_infra.assert_called_once_with("emp-1")
        assert result == expected

    def test_returns_empty_list_when_infra_returns_empty(self):
        """get_my_payslips retourne [] si l'infra retourne []."""
        with patch(
            "app.modules.payslips.application.queries._get_my_payslips",
            return_value=[],
        ):
            result = get_my_payslips("emp-unknown")
        assert result == []


class TestGetEmployeePayslipsQuery:
    """Tests de la query get_employee_payslips."""

    def test_returns_list_from_infra(self):
        """get_employee_payslips retourne la liste renvoyée par l'infrastructure."""
        expected = [
            {"id": "ps-1", "name": "Bulletin_03-2024.pdf", "month": 3, "year": 2024, "url": "https://signed.url/1"},
        ]
        with patch(
            "app.modules.payslips.application.queries._get_employee_payslips",
            return_value=expected,
        ) as mock_infra:
            result = get_employee_payslips("emp-1")
        mock_infra.assert_called_once_with("emp-1")
        assert result == expected

    def test_returns_empty_list_when_infra_returns_empty(self):
        """get_employee_payslips retourne [] si l'infra retourne []."""
        with patch(
            "app.modules.payslips.application.queries._get_employee_payslips",
            return_value=[],
        ):
            result = get_employee_payslips("emp-unknown")
        assert result == []


class TestGetPayslipDetailsQuery:
    """Tests de la query get_payslip_details."""

    def test_returns_detail_when_found(self):
        """get_payslip_details retourne le détail si trouvé."""
        expected = {
            "id": "ps-1",
            "employee_id": "emp-1",
            "company_id": "co-1",
            "name": "Bulletin_03-2024.pdf",
            "month": 3,
            "year": 2024,
            "url": "https://signed.url/1",
            "payslip_data": {"net_a_payer": 2500},
            "edit_history": [],
        }
        with patch(
            "app.modules.payslips.application.queries._get_payslip_details",
            return_value=expected,
        ) as mock_infra:
            result = get_payslip_details("ps-1")
        mock_infra.assert_called_once_with("ps-1")
        assert result == expected

    def test_returns_none_when_not_found(self):
        """get_payslip_details retourne None si bulletin inexistant."""
        with patch(
            "app.modules.payslips.application.queries._get_payslip_details",
            return_value=None,
        ):
            result = get_payslip_details("ps-unknown")
        assert result is None


class TestGetPayslipHistoryQuery:
    """Tests de la query get_payslip_history."""

    def test_returns_history_list_from_infra(self):
        """get_payslip_history retourne la liste d'historique."""
        expected = [
            {"version": 1, "edited_at": "2024-03-15T10:00:00", "edited_by": "user-1", "changes_summary": "Création"},
            {"version": 2, "edited_at": "2024-03-20T14:00:00", "edited_by": "user-2", "changes_summary": "Modif brut"},
        ]
        with patch(
            "app.modules.payslips.application.queries._get_payslip_history",
            return_value=expected,
        ) as mock_infra:
            result = get_payslip_history("ps-1")
        mock_infra.assert_called_once_with("ps-1")
        assert result == expected
        assert len(result) == 2

    def test_returns_empty_list_when_no_history(self):
        """get_payslip_history retourne [] si pas d'historique."""
        with patch(
            "app.modules.payslips.application.queries._get_payslip_history",
            return_value=[],
        ):
            result = get_payslip_history("ps-1")
        assert result == []
