"""
Tests de câblage (wiring) du module payslips.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> application -> commands/queries -> infrastructure) fonctionnent.
"""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-payslips-wiring"
TEST_EMPLOYEE_ID = "emp-wiring"


def _employee_user():
    """Utilisateur = employé (pour GET /api/me/payslips)."""
    return User(
        id=TEST_EMPLOYEE_ID,
        email="emp@wiring.test",
        first_name="Jean",
        last_name="Wiring",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Wiring Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


def _rh_user():
    """Utilisateur RH (pour détail / edit / history / restore)."""
    return User(
        id="rh-wiring",
        email="rh@wiring.test",
        first_name="RH",
        last_name="Wiring",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Wiring Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestPayslipsWiringGenerate:
    """Flux POST /api/actions/generate-payslip -> generate_payslip (command) -> provider."""

    def test_generate_flow_uses_command_and_provider(self, client: TestClient):
        """La route appelle generate_payslip qui utilise employee_statut_reader et provider."""
        with patch(
            "app.modules.payslips.application.commands.employee_statut_reader"
        ) as mock_reader, patch(
            "app.modules.payslips.application.commands.payslip_generator_provider"
        ) as mock_provider:
            mock_reader.get_employee_statut.return_value = "Cadre forfait jour"
            mock_provider.generate_forfait.return_value = {
                "status": "ok",
                "message": "Généré",
                "download_url": "https://wiring.signed/pdf",
            }
            response = client.post(
                "/api/actions/generate-payslip",
                json={"employee_id": "emp-1", "year": 2024, "month": 3},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["download_url"] == "https://wiring.signed/pdf"
        mock_reader.get_employee_statut.assert_called_once_with("emp-1")
        mock_provider.generate_forfait.assert_called_once_with(
            employee_id="emp-1", year=2024, month=3
        )


class TestPayslipsWiringMyPayslips:
    """Flux GET /api/me/payslips -> get_my_payslips (query) -> infrastructure queries."""

    def test_my_payslips_flow_uses_query(self, client: TestClient):
        """La route appelle get_my_payslips avec current_user.id."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.get_my_payslips"
        ) as mock_get:
            mock_get.return_value = [
                {"id": "ps-1", "name": "B.pdf", "month": 3, "year": 2024, "url": "https://u.fr", "net_a_payer": 2500.0},
            ]
            app.dependency_overrides[get_current_user] = lambda: _employee_user()
            try:
                response = client.get("/api/me/payslips")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()[0]["id"] == "ps-1"
        mock_get.assert_called_once_with(TEST_EMPLOYEE_ID)


class TestPayslipsWiringDetailAndAuth:
    """Flux GET /api/payslips/{id} -> get_payslip_details_for_user -> can_view_payslip + get_payslip_details."""

    def test_detail_flow_uses_service_and_returns_detail(self, client: TestClient):
        """La route construit UserContext, appelle get_payslip_details_for_user, retourne le détail."""
        from app.core.security import get_current_user

        detail = {
            "id": "ps-1",
            "employee_id": "emp-1",
            "company_id": TEST_COMPANY_ID,
            "name": "Bulletin_03-2024.pdf",
            "month": 3,
            "year": 2024,
            "url": "https://signed.url",
            "pdf_storage_path": "path",
            "payslip_data": {},
            "manually_edited": False,
            "edit_count": 0,
            "edited_at": None,
            "edited_by": None,
            "internal_notes": [],
            "pdf_notes": None,
            "edit_history": [],
            "cumuls": None,
        }
        with patch(
            "app.modules.payslips.api.router.get_payslip_details_for_user",
            return_value=detail,
        ) as mock_get:
            app.dependency_overrides[get_current_user] = lambda: _rh_user()
            try:
                response = client.get("/api/payslips/ps-1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["id"] == "ps-1"
        mock_get.assert_called_once()
        call_args = mock_get.call_args[0]
        assert call_args[0] == "ps-1"
        assert call_args[1].user_id == "rh-wiring"
        assert call_args[1].active_company_id == TEST_COMPANY_ID


class TestPayslipsWiringDelete:
    """Flux DELETE /api/payslips/{id} -> delete_payslip (command) -> repository."""

    def test_delete_flow_uses_repository(self, client: TestClient):
        """La route appelle delete_payslip qui appelle le repository."""
        with patch(
            "app.modules.payslips.infrastructure.repository.payslip_repository"
        ) as mock_repo:
            response = client.delete("/api/payslips/ps-123")
        assert response.status_code == 204
        mock_repo.delete.assert_called_once_with("ps-123")
