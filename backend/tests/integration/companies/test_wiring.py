"""
Tests de câblage (wiring) du module companies.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> service / queries / commands -> repository / provider) fonctionnent.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"
TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"


def _rh_user():
    """Utilisateur RH avec active_company_id et droits RH."""
    return User(
        id=TEST_USER_ID,
        email="rh@wiring.com",
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


class TestCompaniesWiringDetails:
    """Flux GET /api/company/details : router -> resolve_company_id_for_user -> queries -> fetch_company + compute_kpis."""

    def test_details_flow_uses_active_company_and_returns_company_data_and_kpis(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        company_data = {"id": TEST_COMPANY_ID, "company_name": "Wiring Co"}
        with patch(
            "app.modules.companies.application.queries.fetch_company_with_employees_and_payslips",
            return_value={
                "company_data": company_data,
                "employees": [
                    {"id": "e1", "contract_type": "CDI", "job_title": "Dev"}
                ],
                "payslips": [],
            },
        ):
            app.dependency_overrides[get_current_user] = lambda: _rh_user()
            try:
                response = client.get("/api/company/details")
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data["company_data"] == company_data
        assert data["kpis"]["total_employees"] == 1
        assert "evolution_12_months" in data["kpis"]


class TestCompaniesWiringSettingsGet:
    """Flux GET /api/company/settings : router -> resolve_company_id_for_user -> queries.get_company_settings -> repository."""

    def test_settings_get_flow_uses_active_company_and_repository(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {"medical_follow_up_enabled": True}
        with patch(
            "app.modules.companies.application.queries.company_repository",
            mock_repo,
        ):
            app.dependency_overrides[get_current_user] = lambda: _rh_user()
            try:
                response = client.get("/api/company/settings")
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["medical_follow_up_enabled"] is True
        mock_repo.get_settings.assert_called_once_with(TEST_COMPANY_ID)


class TestCompaniesWiringSettingsPatch:
    """Flux PATCH /api/company/settings : router -> resolve_company_id -> vérif RH -> commands.update_company_settings -> repository."""

    def test_settings_patch_flow_calls_repository_and_returns_updated(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        mock_repo.get_settings.return_value = {"medical_follow_up_enabled": False}
        mock_repo.update_settings.return_value = None
        with patch(
            "app.modules.companies.application.commands.company_repository",
            mock_repo,
        ):
            app.dependency_overrides[get_current_user] = lambda: _rh_user()
            try:
                response = client.patch(
                    "/api/company/settings",
                    json={"medical_follow_up_enabled": True},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["medical_follow_up_enabled"] is True
        mock_repo.get_settings.assert_called_once_with(TEST_COMPANY_ID)
        mock_repo.update_settings.assert_called_once()
        call_settings = mock_repo.update_settings.call_args[0][1]
        assert call_settings["medical_follow_up_enabled"] is True


class TestCompaniesWiringDetailsPatch:
    """Flux PATCH /api/company/details : router -> commands.update_company_details -> repository."""

    def test_details_patch_flow_persists_signatory_fields(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_repo = MagicMock()
        updated_row = {
            "id": TEST_COMPANY_ID,
            "company_name": "Wiring Co",
            "nom_signataire_rh": "Gerault Verny",
            "qualite_signataire_rh": "Gérant",
        }
        mock_repo.update_company.return_value = updated_row
        payload = {
            "adresse_rue": "13 place des 4 dauphins",
            "adresse_code_postal": "13100",
            "adresse_ville": "Aix en Provence",
            "phone": "0778193162",
            "nom_signataire_rh": "Gerault Verny",
            "qualite_signataire_rh": "Gérant",
        }
        with patch(
            "app.modules.companies.application.commands.company_repository",
            mock_repo,
        ), patch(
            "app.modules.companies.application.queries.fetch_company_with_employees_and_payslips",
            return_value={
                "company_data": updated_row,
                "employees": [],
                "payslips": [],
            },
        ):
            app.dependency_overrides[get_current_user] = lambda: _rh_user()
            try:
                response = client.patch(
                    "/api/company/details",
                    json=payload,
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_repo.update_company.assert_called_once()
        update_data = mock_repo.update_company.call_args[0][1]
        assert update_data["nom_signataire_rh"] == "Gerault Verny"
        assert update_data["qualite_signataire_rh"] == "Gérant"
        assert response.json()["company_data"]["nom_signataire_rh"] == "Gerault Verny"
