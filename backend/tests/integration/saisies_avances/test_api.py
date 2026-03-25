"""
Tests d'intégration HTTP des routes du module saisies_avances.

Routes : GET/POST/PATCH/DELETE /api/saisies-avances/salary-seizures*,
GET/POST/PATCH /api/saisies-avances/salary-advances*, /employees/me/*,
/advance-payments*, /payslips/*/deductions|advance-repayments.
Utilise : client (TestClient), dependency_overrides pour get_current_user,
et mocks des commands/queries pour éviter la DB réelle.

Fixture à ajouter dans conftest.py si besoin de tests E2E avec token réel :
  saisies_avances_headers : en-têtes pour utilisateur avec active_company_id
  et droits RH (ou collaborateur pour /me). Format :
  {"Authorization": "Bearer <jwt>", "X-Active-Company": "<company_id>"}.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440002"


def _salary_seizure_row(**overrides):
    """Dict conforme au schéma SalarySeizure pour les mocks."""
    from datetime import datetime

    d = {
        "id": "s1",
        "company_id": TEST_COMPANY_ID,
        "employee_id": TEST_EMPLOYEE_ID,
        "type": "pension_alimentaire",
        "reference_legale": None,
        "creditor_name": "Créancier",
        "creditor_iban": None,
        "amount": 100.0,
        "calculation_mode": "fixe",
        "percentage": None,
        "start_date": "2025-01-01",
        "end_date": None,
        "status": "active",
        "priority": 2,
        "document_url": None,
        "notes": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "created_by": TEST_USER_ID,
    }
    d.update(overrides)
    return d


def _salary_advance_row(**overrides):
    """Dict conforme au schéma SalaryAdvance pour les mocks."""
    from datetime import datetime

    d = {
        "id": "a1",
        "company_id": TEST_COMPANY_ID,
        "employee_id": TEST_EMPLOYEE_ID,
        "requested_amount": 200.0,
        "approved_amount": None,
        "requested_date": "2025-03-01",
        "payment_date": None,
        "payment_method": None,
        "status": "pending",
        "repayment_mode": "single",
        "repayment_months": 1,
        "remaining_amount": 0.0,
        "remaining_to_pay": 0.0,
        "request_comment": None,
        "rejection_reason": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "approved_by": None,
        "approved_at": None,
    }
    d.update(overrides)
    return d


def _make_rh_user(company_id: str = TEST_COMPANY_ID, user_id: str = TEST_USER_ID):
    return User(
        id=user_id,
        email="rh@saisies-test.com",
        first_name="RH",
        last_name="Saisies",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


def _make_collaborator_user(
    company_id: str = TEST_COMPANY_ID, user_id: str = TEST_EMPLOYEE_ID
):
    return User(
        id=user_id,
        email="emp@saisies-test.com",
        first_name="Emp",
        last_name="Saisies",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=company_id,
                company_name="Test Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=company_id,
    )


BASE = "/api/saisies-avances"


class TestSaisiesAvancesUnauthenticated:
    """Sans token : routes protégées renvoient 401."""

    def test_get_salary_seizures_401(self, client: TestClient):
        response = client.get(f"{BASE}/salary-seizures")
        assert response.status_code == 401

    def test_post_salary_seizure_401(self, client: TestClient):
        response = client.post(
            f"{BASE}/salary-seizures",
            json={
                "employee_id": TEST_EMPLOYEE_ID,
                "type": "pension_alimentaire",
                "creditor_name": "Créancier",
                "amount": 100,
                "start_date": "2025-01-01",
                "priority": 2,
            },
        )
        assert response.status_code == 401

    def test_get_my_salary_advances_401(self, client: TestClient):
        response = client.get(f"{BASE}/employees/me/salary-advances")
        assert response.status_code == 401

    def test_post_salary_advance_401(self, client: TestClient):
        response = client.post(
            f"{BASE}/salary-advances",
            json={
                "employee_id": TEST_EMPLOYEE_ID,
                "requested_amount": 200,
                "requested_date": "2025-03-01",
                "repayment_mode": "single",
            },
        )
        assert response.status_code == 401


class TestCalculateSeizablePublic:
    """POST /salary-seizures/calculate-seizable : pas d'auth requise."""

    def test_calculate_seizable_returns_200_and_calculation(self, client: TestClient):
        response = client.post(
            f"{BASE}/salary-seizures/calculate-seizable",
            json={"net_salary": 2000, "dependents_count": 0},
        )
        assert response.status_code == 200
        data = response.json()
        assert "seizable_amount" in data
        assert "minimum_untouchable" in data
        # JSON peut sérialiser Decimal en nombre ou chaîne
        assert data["net_salary"] == 2000 or data["net_salary"] == "2000"
        assert float(data["seizable_amount"]) > 0


class TestSalarySeizuresAPI:
    """Routes saisies sur salaire (avec auth mockée + commands/queries mockés)."""

    def test_get_salary_seizures_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_salary_seizures"
        ) as q:
            q.return_value = [_salary_seizure_row()]
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/salary-seizures")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["creditor_name"] == "Créancier"

    def test_get_salary_seizure_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_salary_seizure"
        ) as q:
            q.return_value = _salary_seizure_row(creditor_name="Créancier")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/salary-seizures/s1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["creditor_name"] == "Créancier"

    def test_get_salary_seizure_404(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.saisies_avances.application.dto import NotFoundError

        with patch(
            "app.modules.saisies_avances.application.queries.get_salary_seizure"
        ) as q:
            q.side_effect = NotFoundError("Saisie non trouvée.")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/salary-seizures/s-inexistant")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404

    def test_post_salary_seizure_201(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.create_salary_seizure"
        ) as cmd:
            cmd.return_value = _salary_seizure_row(id="s-new")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    f"{BASE}/salary-seizures",
                    json={
                        "employee_id": TEST_EMPLOYEE_ID,
                        "type": "pension_alimentaire",
                        "creditor_name": "Créancier",
                        "amount": 100,
                        "start_date": "2025-01-01",
                        "priority": 2,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201
        assert response.json()["id"] == "s-new"

    def test_patch_salary_seizure_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.update_salary_seizure"
        ) as cmd:
            cmd.return_value = _salary_seizure_row(status="suspended")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.patch(
                    f"{BASE}/salary-seizures/s1",
                    json={"status": "suspended"},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_delete_salary_seizure_204(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.delete_salary_seizure"
        ) as cmd:
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.delete(f"{BASE}/salary-seizures/s1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 204
        cmd.assert_called_once_with("s1")


class TestSalaryAdvancesAPI:
    """Routes avances sur salaire."""

    def test_get_salary_advances_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_salary_advances"
        ) as q:
            q.return_value = [_salary_advance_row()]
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/salary-advances")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_salary_advance_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_salary_advance"
        ) as q:
            q.return_value = _salary_advance_row(
                status="approved", requested_amount=200.0
            )
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/salary-advances/a1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_post_salary_advance_201(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.create_salary_advance"
        ) as cmd:
            cmd.return_value = _salary_advance_row(id="a-new", status="pending")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    f"{BASE}/salary-advances",
                    json={
                        "employee_id": TEST_EMPLOYEE_ID,
                        "requested_amount": 200,
                        "requested_date": "2025-03-01",
                        "repayment_mode": "single",
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201

    def test_patch_approve_salary_advance_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.approve_salary_advance"
        ) as cmd:
            cmd.return_value = _salary_advance_row(status="approved")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.patch(f"{BASE}/salary-advances/a1/approve")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_patch_reject_salary_advance_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.reject_salary_advance"
        ) as cmd:
            cmd.return_value = _salary_advance_row(status="rejected")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.patch(
                    f"{BASE}/salary-advances/a1/reject",
                    json={"rejection_reason": "Budget insuffisant"},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200


class TestEmployeesMeAPI:
    """Routes /employees/me/* (collaborateur)."""

    def test_get_my_salary_advances_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_my_salary_advances"
        ) as q:
            q.return_value = [_salary_advance_row()]
            app.dependency_overrides[get_current_user] = lambda: (
                _make_collaborator_user()
            )
            try:
                response = client.get(f"{BASE}/employees/me/salary-advances")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_get_my_advance_available_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_my_advance_available"
        ) as q:
            from app.modules.saisies_avances.schemas import AdvanceAvailableAmount

            q.return_value = AdvanceAvailableAmount(
                available_amount=Decimal("500"),
                daily_salary=Decimal("50"),
                days_worked=Decimal("15"),
                outstanding_advances=Decimal("0"),
                max_advance_days=10,
            )
            app.dependency_overrides[get_current_user] = lambda: (
                _make_collaborator_user()
            )
            try:
                response = client.get(f"{BASE}/employees/me/advance-available")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert "available_amount" in data


class TestEmployeeSalarySeizuresAdvances:
    """Routes /employees/{employee_id}/salary-seizures et salary-advances."""

    def test_get_employee_salary_seizures_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_employee_salary_seizures"
        ) as q:
            q.return_value = []
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(
                    f"{BASE}/employees/{TEST_EMPLOYEE_ID}/salary-seizures"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_get_employee_salary_advances_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_employee_salary_advances"
        ) as q:
            q.return_value = []
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(
                    f"{BASE}/employees/{TEST_EMPLOYEE_ID}/salary-advances"
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200


class TestPayslipsDeductionsRepayments:
    """Routes /payslips/{payslip_id}/deductions et advance-repayments."""

    def test_get_payslip_deductions_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_payslip_deductions"
        ) as q:
            q.return_value = []
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/payslips/ps1/deductions")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_get_payslip_advance_repayments_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_payslip_advance_repayments"
        ) as q:
            q.return_value = []
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/payslips/ps1/advance-repayments")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200


class TestAdvancePaymentsAPI:
    """Routes upload-url, POST/GET/DELETE advance-payments."""

    def test_post_upload_url_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.get_payment_upload_url"
        ) as cmd:
            cmd.return_value = {"path": "u/file.pdf", "signedURL": "https://signed"}
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    f"{BASE}/advance-payments/upload-url",
                    json={"filename": "preuve.pdf"},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert "signedURL" in response.json()

    def test_post_advance_payment_201(self, client: TestClient):
        from app.core.security import get_current_user
        from datetime import datetime

        with patch(
            "app.modules.saisies_avances.application.commands.create_advance_payment"
        ) as cmd:
            cmd.return_value = {
                "id": "pay-1",
                "advance_id": "a1",
                "company_id": TEST_COMPANY_ID,
                "payment_amount": 100.0,
                "payment_date": "2025-03-15",
                "payment_method": None,
                "proof_file_path": None,
                "proof_file_name": None,
                "proof_file_type": None,
                "notes": None,
                "created_at": datetime.now().isoformat(),
                "created_by": TEST_USER_ID,
            }
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    f"{BASE}/advance-payments",
                    json={
                        "advance_id": "a1",
                        "payment_amount": 100,
                        "payment_date": "2025-03-15",
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 201

    def test_get_advance_payments_200(self, client: TestClient):
        from app.core.security import get_current_user
        from datetime import datetime

        with patch(
            "app.modules.saisies_avances.application.queries.get_advance_payments"
        ) as q:
            q.return_value = [
                {
                    "id": "pay-1",
                    "advance_id": "a1",
                    "company_id": TEST_COMPANY_ID,
                    "payment_amount": 100.0,
                    "payment_date": "2025-03-15",
                    "payment_method": None,
                    "proof_file_path": None,
                    "proof_file_name": None,
                    "proof_file_type": None,
                    "notes": None,
                    "created_at": datetime.now().isoformat(),
                    "created_by": TEST_USER_ID,
                }
            ]
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/advances/a1/payments")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200

    def test_get_payment_proof_url_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.queries.get_payment_proof_url"
        ) as q:
            q.return_value = "https://signed/download"
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get(f"{BASE}/advance-payments/pay-1/proof-url")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["url"] == "https://signed/download"

    def test_delete_advance_payment_200(self, client: TestClient):
        from app.core.security import get_current_user

        with patch(
            "app.modules.saisies_avances.application.commands.delete_advance_payment"
        ) as cmd:
            cmd.return_value = {"success": True}
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.delete(f"{BASE}/advance-payments/pay-1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
