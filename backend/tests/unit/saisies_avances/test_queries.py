"""
Tests des requêtes du module saisies_avances (application/queries.py).

Chaque query est testée avec repositories et providers mockés (patch au niveau
du module service utilisé par les queries).
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.modules.saisies_avances.application import queries


SERVICE_MODULE = "app.modules.saisies_avances.application.service"


class TestGetSalarySeizures:
    """Query get_salary_seizures."""

    def test_returns_list_from_service(self):
        with patch(f"{SERVICE_MODULE}.list_seizures_with_employee") as list_fn:
            list_fn.return_value = [{"id": "s1", "employee_name": "Jean Dupont"}]
            result = queries.get_salary_seizures(employee_id="emp-1", status="active")
        assert len(result) == 1
        assert result[0]["id"] == "s1"
        list_fn.assert_called_once_with(employee_id="emp-1", status="active")


class TestGetSalarySeizure:
    """Query get_salary_seizure."""

    def test_returns_seizure_by_id(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            repo.get_by_id.return_value = {"id": "s1", "creditor_name": "Créancier"}
            result = queries.get_salary_seizure("s1")
        assert result["id"] == "s1"
        assert result["creditor_name"] == "Créancier"

    def test_not_found_raises(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            repo.get_by_id.return_value = None
            with pytest.raises(Exception) as exc_info:
                queries.get_salary_seizure("s-inexistant")
            assert "Saisie" in str(exc_info.value) or "non trouvée" in str(exc_info.value)


class TestGetEmployeeSalarySeizures:
    """Query get_employee_salary_seizures."""

    def test_returns_list_for_employee(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            repo.list_.return_value = [{"id": "s1"}, {"id": "s2"}]
            result = queries.get_employee_salary_seizures("emp-1")
        assert len(result) == 2
        repo.list_.assert_called_once_with(employee_id="emp-1")


class TestGetMySalaryAdvances:
    """Query get_my_salary_advances."""

    def test_returns_list_for_employee(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.list_.return_value = [{"id": "a1", "status": "pending"}]
            result = queries.get_my_salary_advances("emp-1")
        assert len(result) == 1
        assert result[0]["status"] == "pending"
        repo.list_.assert_called_once_with(employee_id="emp-1")


class TestGetMyAdvanceAvailable:
    """Query get_my_advance_available."""

    def test_returns_advance_available_amount(self):
        with patch(f"{SERVICE_MODULE}.build_advance_available") as build:
            build.return_value = {
                "daily_salary": Decimal("50"),
                "days_worked": Decimal("15"),
                "outstanding_advances": Decimal("0"),
                "available_amount": Decimal("750"),
                "max_advance_days": 10,
            }
            with patch(f"{SERVICE_MODULE}.infra_mappers") as mappers:
                from app.modules.saisies_avances.schemas import AdvanceAvailableAmount
                mappers.to_advance_available_amount.return_value = AdvanceAvailableAmount(
                    daily_salary=Decimal("50"),
                    days_worked=Decimal("15"),
                    outstanding_advances=Decimal("0"),
                    available_amount=Decimal("750"),
                    max_advance_days=10,
                )
                result = queries.get_my_advance_available("emp-1")
        assert result.available_amount == Decimal("750")


class TestGetSalaryAdvances:
    """Query get_salary_advances."""

    def test_returns_list_with_remaining_to_pay(self):
        with patch(f"{SERVICE_MODULE}.list_advances_with_employee_and_remaining_to_pay") as list_fn:
            list_fn.return_value = [{"id": "a1", "remaining_to_pay": 100.0}]
            result = queries.get_salary_advances(employee_id="emp-1", status="approved")
        assert len(result) == 1
        assert result[0]["remaining_to_pay"] == 100.0
        list_fn.assert_called_once_with(employee_id="emp-1", status="approved")


class TestGetSalaryAdvance:
    """Query get_salary_advance."""

    def test_returns_advance_by_id(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.get_by_id.return_value = {"id": "a1", "requested_amount": 200}
            result = queries.get_salary_advance("a1")
        assert result["id"] == "a1"
        assert result["requested_amount"] == 200

    def test_not_found_raises(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.get_by_id.return_value = None
            with pytest.raises(Exception) as exc_info:
                queries.get_salary_advance("a-inexistant")
            assert "Avance" in str(exc_info.value) or "non trouvée" in str(exc_info.value)


class TestGetEmployeeSalaryAdvances:
    """Query get_employee_salary_advances."""

    def test_returns_list_for_employee(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.list_.return_value = [{"id": "a1"}]
            result = queries.get_employee_salary_advances("emp-1")
        assert len(result) == 1

    def test_employee_id_me_raises(self):
        with pytest.raises(Exception) as exc_info:
            queries.get_employee_salary_advances("me")
        assert "me" in str(exc_info.value).lower() or "employees/me" in str(exc_info.value).lower()


class TestGetPayslipDeductions:
    """Query get_payslip_deductions."""

    def test_returns_deductions_list(self):
        with patch(f"{SERVICE_MODULE}.list_salary_seizure_deductions_by_payslip") as list_fn:
            list_fn.return_value = [{"id": "d1", "deducted_amount": 50}]
            result = queries.get_payslip_deductions("payslip-1")
        assert len(result) == 1
        assert result[0]["deducted_amount"] == 50
        list_fn.assert_called_once_with("payslip-1")


class TestGetPayslipAdvanceRepayments:
    """Query get_payslip_advance_repayments."""

    def test_returns_repayments_list(self):
        with patch(f"{SERVICE_MODULE}.list_salary_advance_repayments_by_payslip") as list_fn:
            list_fn.return_value = [{"id": "r1", "repayment_amount": 100}]
            result = queries.get_payslip_advance_repayments("payslip-1")
        assert len(result) == 1
        list_fn.assert_called_once_with("payslip-1")


class TestGetAdvancePayments:
    """Query get_advance_payments."""

    def test_returns_payments_for_advance(self):
        with patch(f"{SERVICE_MODULE}.advance_payment_repository") as repo:
            repo.list_by_advance_id.return_value = [{"id": "p1", "payment_amount": 100}]
            result = queries.get_advance_payments("adv-1")
        assert len(result) == 1
        repo.list_by_advance_id.assert_called_once_with("adv-1")


class TestGetPaymentProofUrl:
    """Query get_payment_proof_url."""

    def test_returns_signed_url(self):
        with patch(f"{SERVICE_MODULE}.get_proof_file_path", return_value="u/file.pdf"):
            with patch(f"{SERVICE_MODULE}.advance_payment_storage") as storage:
                storage.create_signed_download_url.return_value = "https://signed/download"
                result = queries.get_payment_proof_url("pay-1")
        assert result == "https://signed/download"

    def test_no_proof_path_raises(self):
        with patch(f"{SERVICE_MODULE}.get_proof_file_path", return_value=None):
            with pytest.raises(Exception) as exc_info:
                queries.get_payment_proof_url("pay-1")
            assert "Preuve" in str(exc_info.value) or "non trouvée" in str(exc_info.value)


class TestCalculateSeizable:
    """Query calculate_seizable."""

    def test_returns_seizable_calculation(self):
        with patch(f"{SERVICE_MODULE}.domain_rules") as rules:
            with patch(f"{SERVICE_MODULE}.infra_mappers") as mappers:
                rules.calculate_seizable_amount.return_value = Decimal("250")
                from app.modules.saisies_avances.schemas import SeizableAmountCalculation
                mappers.to_seizable_amount_calculation.return_value = SeizableAmountCalculation(
                    net_salary=Decimal("2000"),
                    dependents_count=0,
                    adjusted_salary=Decimal("2000"),
                    seizable_amount=Decimal("250"),
                    minimum_untouchable=Decimal("100"),
                )
                result = queries.calculate_seizable(Decimal("2000"), dependents_count=0)
        assert result.seizable_amount == Decimal("250")
        rules.calculate_seizable_amount.assert_called_once_with(Decimal("2000"), 0)
