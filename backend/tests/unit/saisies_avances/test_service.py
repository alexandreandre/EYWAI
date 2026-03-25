"""
Tests du service applicatif saisies_avances (application/service.py).

Service orchestrant domain + infrastructure. Les dépendances (repositories,
queries, storage) sont mockées.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.modules.saisies_avances.application import service
from app.modules.saisies_avances.application.dto import UserContext


SERVICE_MODULE = "app.modules.saisies_avances.application.service"
COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"
EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440002"


class TestGetSalarySeizure:
    """Service get_salary_seizure."""

    def test_returns_row_when_found(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            row = {"id": "s1", "creditor_name": "Créancier"}
            repo.get_by_id.return_value = row
            result = service.get_salary_seizure("s1")
        assert result == row

    def test_raises_not_found_when_missing(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            repo.get_by_id.return_value = None
            with pytest.raises(service.NotFoundError) as exc_info:
                service.get_salary_seizure("s-inexistant")
            assert "Saisie" in str(exc_info.value)


class TestGetSalaryAdvance:
    """Service get_salary_advance."""

    def test_returns_row_when_found(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            row = {"id": "a1", "status": "pending"}
            repo.get_by_id.return_value = row
            result = service.get_salary_advance("a1")
        assert result == row

    def test_raises_not_found_when_missing(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.get_by_id.return_value = None
            with pytest.raises(service.NotFoundError) as exc_info:
                service.get_salary_advance("a-inexistant")
            assert "Avance" in str(exc_info.value)


class TestGetEmployeeSalaryAdvances:
    """Service get_employee_salary_advances."""

    def test_me_raises_not_found(self):
        with pytest.raises(service.NotFoundError) as exc_info:
            service.get_employee_salary_advances("me")
        assert "me" in str(exc_info.value).lower() or "salary-advances" in str(exc_info.value).lower()


class TestCalculateSeizable:
    """Service calculate_seizable (règles pures + mapper)."""

    def test_returns_seizable_amount_calculation(self):
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
                result = service.calculate_seizable(Decimal("2000"), dependents_count=0)
        assert result.seizable_amount == Decimal("250")
        assert result.minimum_untouchable == Decimal("100")


class TestCreateSalaryAdvanceForbidden:
    """Service create_salary_advance - cas Forbidden."""

    def test_collaborator_creating_for_other_raises_forbidden(self):
        from app.modules.saisies_avances.schemas import SalaryAdvanceCreate
        advance_data = SalaryAdvanceCreate(
            employee_id="other-id",
            requested_amount=Decimal("100"),
            requested_date=date(2025, 3, 1),
        )
        ctx = UserContext(user_id=USER_ID, role="collaborateur")
        with pytest.raises(service.ForbiddenError) as exc_info:
            service.create_salary_advance(advance_data, ctx)
        assert "vous-même" in str(exc_info.value).lower()


class TestCreateSalaryAdvanceNotFound:
    """Service create_salary_advance - employé non trouvé."""

    def test_employee_not_found_raises_not_found(self):
        from app.modules.saisies_avances.schemas import SalaryAdvanceCreate
        advance_data = SalaryAdvanceCreate(
            employee_id=EMPLOYEE_ID,
            requested_amount=Decimal("100"),
            requested_date=date(2025, 3, 1),
        )
        ctx = UserContext(user_id=USER_ID, role="rh")
        with patch(f"{SERVICE_MODULE}.employee_company_provider") as prov:
            prov.get_company_id.return_value = None
            with pytest.raises(service.NotFoundError) as exc_info:
                service.create_salary_advance(advance_data, ctx)
            assert "Employé" in str(exc_info.value)


class TestApproveSalaryAdvanceValidation:
    """Service approve_salary_advance - statut non pending."""

    def test_advance_not_pending_raises_validation(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.get_by_id.return_value = {"id": "a1", "status": "approved", "requested_amount": 100}
            with pytest.raises(service.ValidationError) as exc_info:
                service.approve_salary_advance("a1", USER_ID)
            assert "approuvée" in str(exc_info.value).lower()
