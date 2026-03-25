"""
Tests des commandes du module saisies_avances (application/commands.py).

Chaque commande est testée avec repositories et providers mockés (patch au niveau
du module service).
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.modules.saisies_avances.application import commands
from app.modules.saisies_avances.application.dto import UserContext
from app.modules.saisies_avances.schemas import (
    SalaryAdvanceCreate,
    SalaryAdvancePaymentCreate,
    SalarySeizureCreate,
    SalarySeizureUpdate,
)


SERVICE_MODULE = "app.modules.saisies_avances.application.service"
COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
USER_ID = "660e8400-e29b-41d4-a716-446655440001"
EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440002"


def _seizure_create(
    employee_id: str = EMPLOYEE_ID,
    type: str = "pension_alimentaire",
    amount: Decimal = Decimal("100"),
    start_date: date = date(2025, 1, 1),
):
    return SalarySeizureCreate(
        employee_id=employee_id,
        type=type,
        creditor_name="Créancier Test",
        amount=amount,
        calculation_mode="fixe",
        start_date=start_date,
        priority=2,
    )


def _advance_create(
    employee_id: str = EMPLOYEE_ID,
    requested_amount: Decimal = Decimal("200"),
    requested_date: date = date(2025, 3, 1),
):
    return SalaryAdvanceCreate(
        employee_id=employee_id,
        requested_amount=requested_amount,
        requested_date=requested_date,
        repayment_mode="single",
    )


class TestCreateSalarySeizure:
    """Commande create_salary_seizure."""

    def test_create_salary_seizure_returns_created_row(self):
        seizure_data = _seizure_create()
        created = {"id": "seiz-1", "employee_id": EMPLOYEE_ID, "status": "active"}
        with patch(f"{SERVICE_MODULE}.employee_company_provider") as prov:
            with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
                prov.get_company_id.return_value = COMPANY_ID
                repo.create.return_value = created
                result = commands.create_salary_seizure(seizure_data, USER_ID)
        assert result == created
        prov.get_company_id.assert_called_once_with(EMPLOYEE_ID)
        repo.create.assert_called_once()
        call_data = repo.create.call_args[0][0]
        assert call_data["company_id"] == COMPANY_ID
        assert call_data["employee_id"] == EMPLOYEE_ID
        assert call_data["status"] == "active"

    def test_create_salary_seizure_employee_not_found_raises(self):
        seizure_data = _seizure_create()
        with patch(f"{SERVICE_MODULE}.employee_company_provider") as prov:
            prov.get_company_id.return_value = None
            with pytest.raises(Exception) as exc_info:
                commands.create_salary_seizure(seizure_data, USER_ID)
            assert "Employé" in str(exc_info.value) or "non trouvé" in str(
                exc_info.value
            )


class TestUpdateSalarySeizure:
    """Commande update_salary_seizure."""

    def test_update_salary_seizure_returns_updated_row(self):
        update_data = SalarySeizureUpdate(status="suspended", notes="Suspendu")
        updated = {"id": "seiz-1", "status": "suspended"}
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            repo.update.return_value = updated
            result = commands.update_salary_seizure("seiz-1", update_data)
        assert result == updated
        repo.update.assert_called_once_with(
            "seiz-1", {"status": "suspended", "notes": "Suspendu"}
        )

    def test_update_salary_seizure_not_found_raises(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            repo.update.return_value = None
            with pytest.raises(Exception) as exc_info:
                commands.update_salary_seizure(
                    "seiz-inexistant", SalarySeizureUpdate(notes="x")
                )
            assert "Saisie" in str(exc_info.value) or "non trouvée" in str(
                exc_info.value
            )


class TestDeleteSalarySeizure:
    """Commande delete_salary_seizure."""

    def test_delete_salary_seizure_calls_repository(self):
        with patch(f"{SERVICE_MODULE}.seizure_repository") as repo:
            commands.delete_salary_seizure("seiz-1")
        repo.delete.assert_called_once_with("seiz-1")


class TestCreateSalaryAdvance:
    """Commande create_salary_advance."""

    def test_create_salary_advance_rh_under_threshold_approved(self):
        advance_data = _advance_create(requested_amount=Decimal("80"))
        ctx = UserContext(user_id=USER_ID, role="rh")
        created = {"id": "adv-1", "status": "approved"}
        with patch(f"{SERVICE_MODULE}.employee_company_provider") as prov:
            with patch(f"{SERVICE_MODULE}.build_advance_available") as build:
                with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
                    prov.get_company_id.return_value = COMPANY_ID
                    build.return_value = {"available_amount": Decimal("500")}
                    repo.create.return_value = created
                    result = commands.create_salary_advance(advance_data, ctx)
        assert result == created
        repo.create.assert_called_once()
        call_data = repo.create.call_args[0][0]
        assert call_data["status"] == "approved"

    def test_create_salary_advance_collaborator_for_self_pending(self):
        advance_data = _advance_create(
            employee_id=USER_ID, requested_amount=Decimal("50")
        )
        ctx = UserContext(user_id=USER_ID, role="collaborateur")
        created = {"id": "adv-2", "status": "pending"}
        with patch(f"{SERVICE_MODULE}.employee_company_provider") as prov:
            with patch(f"{SERVICE_MODULE}.build_advance_available") as build:
                with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
                    prov.get_company_id.return_value = COMPANY_ID
                    build.return_value = {"available_amount": Decimal("200")}
                    repo.create.return_value = created
                    result = commands.create_salary_advance(advance_data, ctx)
        assert result == created
        call_data = repo.create.call_args[0][0]
        assert call_data["status"] == "pending"

    def test_create_salary_advance_collaborator_for_other_forbidden(self):
        advance_data = _advance_create(employee_id="other-employee-id")
        ctx = UserContext(user_id=USER_ID, role="collaborateur")
        with pytest.raises(Exception) as exc_info:
            commands.create_salary_advance(advance_data, ctx)
        assert (
            "vous-même" in str(exc_info.value).lower()
            or "forbidden" in str(exc_info.value).lower()
        )

    def test_create_salary_advance_amount_exceeds_available_raises(self):
        advance_data = _advance_create(
            employee_id=USER_ID, requested_amount=Decimal("300")
        )
        ctx = UserContext(user_id=USER_ID, role="collaborateur")
        with patch(f"{SERVICE_MODULE}.employee_company_provider") as prov:
            with patch(f"{SERVICE_MODULE}.build_advance_available") as build:
                prov.get_company_id.return_value = COMPANY_ID
                build.return_value = {"available_amount": Decimal("100")}
                with pytest.raises(Exception) as exc_info:
                    commands.create_salary_advance(advance_data, ctx)
                assert "Montant" in str(exc_info.value) or "disponible" in str(
                    exc_info.value
                )


class TestApproveSalaryAdvance:
    """Commande approve_salary_advance."""

    def test_approve_salary_advance_returns_updated(self):
        advance = {"id": "adv-1", "status": "pending", "requested_amount": 200.0}
        updated = {"id": "adv-1", "status": "approved"}
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.get_by_id.return_value = advance
            repo.update.return_value = updated
            result = commands.approve_salary_advance("adv-1", USER_ID)
        assert result == updated
        repo.update.assert_called_once()
        call_data = repo.update.call_args[0][1]
        assert call_data["status"] == "approved"

    def test_approve_salary_advance_not_pending_raises(self):
        advance = {"id": "adv-1", "status": "approved"}
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.get_by_id.return_value = advance
            with pytest.raises(Exception) as exc_info:
                commands.approve_salary_advance("adv-1", USER_ID)
            assert "approuvée" in str(exc_info.value).lower() or "Validation" in str(
                type(exc_info.value).__name__
            )


class TestRejectSalaryAdvance:
    """Commande reject_salary_advance."""

    def test_reject_salary_advance_returns_updated(self):
        updated = {"id": "adv-1", "status": "rejected", "rejection_reason": "Budget"}
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.update.return_value = updated
            result = commands.reject_salary_advance("adv-1", "Budget")
        assert result == updated
        repo.update.assert_called_once_with(
            "adv-1", {"status": "rejected", "rejection_reason": "Budget"}
        )

    def test_reject_salary_advance_not_found_raises(self):
        with patch(f"{SERVICE_MODULE}.advance_repository") as repo:
            repo.update.return_value = None
            with pytest.raises(Exception) as exc_info:
                commands.reject_salary_advance("adv-inexistant", "Raison")
            assert "Avance" in str(exc_info.value) or "non trouvée" in str(
                exc_info.value
            )


class TestGetPaymentUploadUrl:
    """Commande get_payment_upload_url."""

    def test_get_payment_upload_url_returns_path_and_signed_url(self):
        with patch(f"{SERVICE_MODULE}.advance_payment_storage") as storage:
            storage.create_signed_upload_url.return_value = {
                "path": "u/f.pdf",
                "signedURL": "https://signed",
            }
            result = commands.get_payment_upload_url("fichier.pdf", USER_ID)
        assert result["path"]
        assert result["signedURL"] == "https://signed"
        storage.create_signed_upload_url.assert_called_once()


class TestCreateAdvancePayment:
    """Commande create_advance_payment."""

    def test_create_advance_payment_returns_payment(self):
        advance = {
            "id": "adv-1",
            "company_id": COMPANY_ID,
            "status": "approved",
            "approved_amount": 500,
        }
        payment_data = SalaryAdvancePaymentCreate(
            advance_id="adv-1",
            payment_amount=Decimal("200"),
            payment_date=date(2025, 3, 15),
        )
        created = {"id": "pay-1", "advance_id": "adv-1"}
        with patch(f"{SERVICE_MODULE}.advance_repository") as adv_repo:
            with patch(f"{SERVICE_MODULE}.advance_payment_repository") as pay_repo:
                adv_repo.get_by_id.return_value = advance
                pay_repo.get_total_paid_by_advance_id.return_value = Decimal("0")
                pay_repo.create.return_value = created
                result = commands.create_advance_payment(payment_data, USER_ID)
        assert result == created
        pay_repo.create.assert_called_once()
        adv_repo.update.assert_called()

    def test_create_advance_payment_exceeds_remaining_raises(self):
        advance = {
            "id": "adv-1",
            "company_id": COMPANY_ID,
            "status": "approved",
            "approved_amount": 200,
        }
        payment_data = SalaryAdvancePaymentCreate(
            advance_id="adv-1",
            payment_amount=Decimal("300"),
            payment_date=date(2025, 3, 15),
        )
        with patch(f"{SERVICE_MODULE}.advance_repository") as adv_repo:
            with patch(f"{SERVICE_MODULE}.advance_payment_repository") as pay_repo:
                adv_repo.get_by_id.return_value = advance
                pay_repo.get_total_paid_by_advance_id.return_value = Decimal("0")
                with pytest.raises(Exception) as exc_info:
                    commands.create_advance_payment(payment_data, USER_ID)
                assert (
                    "montant" in str(exc_info.value).lower()
                    or "reste" in str(exc_info.value).lower()
                )


class TestDeleteAdvancePayment:
    """Commande delete_advance_payment."""

    def test_delete_advance_payment_returns_success(self):
        payment_with_advance = {
            "id": "pay-1",
            "proof_file_path": None,
            "advance": {"id": "adv-1", "approved_amount": 200},
        }
        with patch(
            f"{SERVICE_MODULE}.get_payment_with_advance",
            return_value=payment_with_advance,
        ):
            with patch(f"{SERVICE_MODULE}.advance_payment_repository") as pay_repo:
                with patch(f"{SERVICE_MODULE}.advance_repository"):
                    pay_repo.get_total_paid_by_advance_id.return_value = Decimal("0")
                    result = commands.delete_advance_payment("pay-1")
        assert result == {"success": True}
        pay_repo.delete.assert_called_once_with("pay-1")

    def test_delete_advance_payment_not_found_raises(self):
        with patch(f"{SERVICE_MODULE}.get_payment_with_advance", return_value=None):
            with pytest.raises(Exception) as exc_info:
                commands.delete_advance_payment("pay-inexistant")
            assert "Paiement" in str(exc_info.value) or "non trouvé" in str(
                exc_info.value
            )
