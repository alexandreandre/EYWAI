"""
Tests de câblage (wiring) du module saisies_avances.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> commands/queries -> service -> repositories / rules) fonctionnent
pour ce module.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440002"


def _make_user(user_id: str = TEST_USER_ID, role: str = "rh"):
    return User(
        id=user_id,
        email="user@saisies-test.com",
        first_name="User",
        last_name="Test",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role=role,
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestWiringCalculateSeizable:
    """
    Flux bout en bout : POST /salary-seizures/calculate-seizable.
    Pas d'auth ; le router appelle queries.calculate_seizable -> service.calculate_seizable
    -> domain_rules.calculate_seizable_amount + infra_mappers.
    """

    def test_calculate_seizable_end_to_end_uses_domain_rules(self, client: TestClient):
        # Sans mock : le calcul réel est exécuté (règles pures + mapper)
        response = client.post(
            "/api/saisies-avances/salary-seizures/calculate-seizable",
            json={"net_salary": 1500, "dependents_count": 0},
        )
        assert response.status_code == 200
        data = response.json()
        # Barème : 1500€ -> tranche 1000-2000 -> 50 + (1500-1000)*0.20 = 150
        assert float(data["seizable_amount"]) == 150.0
        assert data["net_salary"] == 1500 or data["net_salary"] == "1500"
        assert data["dependents_count"] == 0
        assert float(data["minimum_untouchable"]) == 75.0  # 1500/20


class TestWiringGetSalarySeizuresWithAuth:
    """
    Flux : GET /salary-seizures avec get_current_user override -> queries.get_salary_seizures
    -> service.get_salary_seizures -> list_seizures_with_employee (mockée).
    """

    def test_get_salary_seizures_wiring_returns_what_service_returns(self, client: TestClient):
        from app.core.security import get_current_user
        from datetime import datetime

        full_row = {
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
            "employee_name": "Jean Dupont",
        }
        with patch("app.modules.saisies_avances.application.service.list_seizures_with_employee") as list_fn:
            list_fn.return_value = [full_row]
            app.dependency_overrides[get_current_user] = lambda: _make_user()
            try:
                response = client.get("/api/saisies-avances/salary-seizures")
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "s1"
        assert data[0]["creditor_name"] == "Créancier"
        # employee_name est enrichi côté service mais le response_model SalarySeizure ne l'expose pas
        list_fn.assert_called_once_with(employee_id=None, status=None)


class TestWiringCreateSalarySeizureCommandFlow:
    """
    Flux : POST /salary-seizures -> commands.create_salary_seizure -> service.create_salary_seizure
    -> employee_company_provider.get_company_id + seizure_repository.create (mockés).
    """

    def test_create_salary_seizure_wiring_command_calls_service_and_returns_201(self, client: TestClient):
        from app.core.security import get_current_user

        with patch("app.modules.saisies_avances.application.service.employee_company_provider") as prov:
            with patch("app.modules.saisies_avances.application.service.seizure_repository") as repo:
                prov.get_company_id.return_value = TEST_COMPANY_ID
                from datetime import datetime
                repo.create.return_value = {
                    "id": "s-new",
                    "company_id": TEST_COMPANY_ID,
                    "employee_id": TEST_EMPLOYEE_ID,
                    "type": "pension_alimentaire",
                    "creditor_name": "Créancier Test",
                    "calculation_mode": "fixe",
                    "start_date": "2025-01-01",
                    "status": "active",
                    "priority": 2,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat(),
                }
                app.dependency_overrides[get_current_user] = lambda: _make_user()
                try:
                    response = client.post(
                        "/api/saisies-avances/salary-seizures",
                        json={
                            "employee_id": TEST_EMPLOYEE_ID,
                            "type": "pension_alimentaire",
                            "creditor_name": "Créancier Test",
                            "amount": 100,
                            "start_date": "2025-01-01",
                            "priority": 2,
                        },
                    )
                finally:
                    app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "s-new"
        prov.get_company_id.assert_called_once_with(TEST_EMPLOYEE_ID)
        repo.create.assert_called_once()
        call_data = repo.create.call_args[0][0]
        assert call_data["company_id"] == TEST_COMPANY_ID
        assert call_data["employee_id"] == TEST_EMPLOYEE_ID
        assert call_data["status"] == "active"


class TestWiringErrorHandling:
    """Conversion des exceptions applicatives en HTTPException."""

    def test_not_found_seizure_returns_404(self, client: TestClient):
        from app.core.security import get_current_user
        from app.modules.saisies_avances.application.dto import NotFoundError

        with patch("app.modules.saisies_avances.application.queries.get_salary_seizure") as q:
            q.side_effect = NotFoundError("Saisie non trouvée.")
            app.dependency_overrides[get_current_user] = lambda: _make_user()
            try:
                response = client.get("/api/saisies-avances/salary-seizures/s-inexistant")
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 404
        assert "Saisie" in response.json().get("detail", "")
