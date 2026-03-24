"""
Tests d'intégration HTTP des routes du module payslips.

Routes : POST /api/actions/generate-payslip, GET /api/me/payslips,
GET /api/employees/{employee_id}/payslips, DELETE /api/payslips/{payslip_id},
GET /api/payslips/{payslip_id}, POST .../edit, GET .../history, POST .../restore,
GET /api/debug-storage/{employee_id}/{year}/{month}.
Utilise : client (TestClient). Pour les routes protégées, dependency_overrides
pour get_current_user et patch des commands/queries/service (pas de JWT ni DB réels).
"""
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_COMPANY_ID = "company-payslips-test"
TEST_RH_USER_ID = "user-rh-payslips-test"
TEST_EMPLOYEE_ID = "emp-payslips-test"


def _make_payslip_detail_mock(payslip_id: str = "ps-1") -> dict:
    """Payload complet compatible avec PayslipDetail (response_model)."""
    return {
        "id": payslip_id,
        "employee_id": TEST_EMPLOYEE_ID,
        "company_id": TEST_COMPANY_ID,
        "name": "Bulletin_03-2024.pdf",
        "month": 3,
        "year": 2024,
        "url": "https://signed.url/1",
        "pdf_storage_path": "co/emp/bulletin.pdf",
        "payslip_data": {"net_a_payer": 2500},
        "manually_edited": True,
        "edit_count": 1,
        "edited_at": None,
        "edited_by": TEST_RH_USER_ID,
        "internal_notes": [],
        "pdf_notes": None,
        "edit_history": [],
        "cumuls": None,
    }


def _make_rh_user():
    """Utilisateur de test avec droits RH sur TEST_COMPANY_ID."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="rh",
        is_primary=True,
    )
    return User(
        id=TEST_RH_USER_ID,
        email="rh@payslips.test",
        first_name="RH",
        last_name="Payslips",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


def _make_employee_user(employee_id: str = TEST_EMPLOYEE_ID):
    """Utilisateur employé (son id = employee_id pour mes bulletins)."""
    access = CompanyAccess(
        company_id=TEST_COMPANY_ID,
        company_name="Test Co",
        role="collaborateur",
        is_primary=True,
    )
    return User(
        id=employee_id,
        email="emp@payslips.test",
        first_name="Jean",
        last_name="Dupont",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[access],
        active_company_id=TEST_COMPANY_ID,
    )


# --- Routes sans auth (ou dont le routeur n'injecte pas get_current_user) ---


class TestPayslipsGenerateRoute:
    """POST /api/actions/generate-payslip."""

    def test_generate_returns_200_with_mock(self, client: TestClient):
        """Génération mockée retourne status/message/download_url."""
        with patch(
            "app.modules.payslips.api.router.generate_payslip"
        ) as mock_gen:
            mock_gen.return_value = MagicMock(
                status="ok",
                message="Bulletin généré",
                download_url="https://storage.example.com/signed.pdf",
            )
            response = client.post(
                "/api/actions/generate-payslip",
                json={"employee_id": "emp-1", "year": 2024, "month": 3},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["message"] == "Bulletin généré"
        assert data["download_url"] == "https://storage.example.com/signed.pdf"

    def test_generate_with_invalid_body_returns_422(self, client: TestClient):
        """Body invalide (mois manquant) → 422."""
        response = client.post(
            "/api/actions/generate-payslip",
            json={"employee_id": "emp-1", "year": 2024},
        )
        assert response.status_code == 422


class TestPayslipsMyPayslipsRoute:
    """GET /api/me/payslips (authentifié)."""

    def test_get_my_payslips_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.get("/api/me/payslips")
        assert response.status_code == 401

    def test_get_my_payslips_returns_200_with_auth(self, client: TestClient):
        """Avec utilisateur injecté et liste mockée → 200 et liste."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.get_my_payslips",
            return_value=[
                {"id": "ps-1", "name": "Bulletin_03-2024.pdf", "month": 3, "year": 2024, "url": "https://u.fr", "net_a_payer": 2500.0},
            ],
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
            try:
                response = client.get("/api/me/payslips")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "ps-1"
        assert data[0]["month"] == 3
        assert data[0]["year"] == 2024


class TestPayslipsEmployeePayslipsRoute:
    """GET /api/employees/{employee_id}/payslips (pas d'auth sur le routeur actuel)."""

    def test_get_employee_payslips_returns_200_with_mock(self, client: TestClient):
        """Liste des bulletins d'un employé (mock) → 200."""
        with patch(
            "app.modules.payslips.api.router.get_employee_payslips",
            return_value=[
                {"id": "ps-1", "name": "B.pdf", "month": 1, "year": 2024, "url": "https://u.fr"},
            ],
        ):
            response = client.get("/api/employees/emp-1/payslips")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["id"] == "ps-1"


class TestPayslipsDeleteRoute:
    """DELETE /api/payslips/{payslip_id}."""

    def test_delete_returns_204_with_mock(self, client: TestClient):
        """Suppression mockée → 204."""
        with patch(
            "app.modules.payslips.api.router.delete_payslip"
        ) as mock_del:
            response = client.delete("/api/payslips/ps-123")
        assert response.status_code == 204
        mock_del.assert_called_once_with("ps-123")


# --- Routes protégées (détail, edit, history, restore) ---


class TestPayslipsDetailRoute:
    """GET /api/payslips/{payslip_id}."""

    def test_get_details_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.get("/api/payslips/ps-1")
        assert response.status_code == 401

    def test_get_details_returns_404_when_not_found(self, client: TestClient):
        """Bulletin inexistant → 404."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.get_payslip_details_for_user"
        ) as mock_get:
            from app.modules.payslips.application.dto import PayslipNotFoundError
            mock_get.side_effect = PayslipNotFoundError("Bulletin non trouvé")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get("/api/payslips/ps-unknown")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404
        assert "Bulletin" in response.json().get("detail", "")

    def test_get_details_returns_403_when_forbidden(self, client: TestClient):
        """Utilisateur sans droit → 403."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.get_payslip_details_for_user"
        ) as mock_get:
            from app.modules.payslips.application.dto import PayslipForbiddenError
            mock_get.side_effect = PayslipForbiddenError("Accès refusé")
            app.dependency_overrides[get_current_user] = lambda: _make_employee_user("other-emp")
            try:
                response = client.get("/api/payslips/ps-1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 403

    def test_get_details_returns_200_when_found(self, client: TestClient):
        """Détail trouvé et autorisé → 200."""
        from app.core.security import get_current_user

        detail = {
            "id": "ps-1",
            "employee_id": TEST_EMPLOYEE_ID,
            "company_id": TEST_COMPANY_ID,
            "name": "Bulletin_03-2024.pdf",
            "month": 3,
            "year": 2024,
            "url": "https://signed.url/1",
            "pdf_storage_path": "co/emp/bulletin.pdf",
            "payslip_data": {"net_a_payer": 2500},
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
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_employee_user()
            try:
                response = client.get("/api/payslips/ps-1")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert response.json()["id"] == "ps-1"
        assert response.json()["month"] == 3


class TestPayslipsEditRoute:
    """POST /api/payslips/{payslip_id}/edit."""

    def test_edit_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.post(
            "/api/payslips/ps-1/edit",
            json={"payslip_data": {"brut": 3000}, "changes_summary": "Modif"},
        )
        assert response.status_code == 401

    def test_edit_returns_200_with_rh_user(self, client: TestClient):
        """Édition en tant que RH (mock) → 200."""
        from app.core.security import get_current_user

        result = {
            "payslip": _make_payslip_detail_mock("ps-1"),
            "new_pdf_url": "https://new.pdf",
        }
        with patch(
            "app.modules.payslips.api.router.edit_payslip_for_user",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/payslips/ps-1/edit",
                    json={
                        "payslip_data": {"salaire_brut": 3000},
                        "changes_summary": "Augmentation brut",
                        "pdf_notes": None,
                        "internal_note": None,
                    },
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "payslip" in data

    def test_edit_returns_404_when_not_found(self, client: TestClient):
        """Bulletin inexistant → 404."""
        from app.core.security import get_current_user

        with patch(
            "app.modules.payslips.api.router.edit_payslip_for_user"
        ) as mock_edit:
            from app.modules.payslips.application.dto import PayslipNotFoundError
            mock_edit.side_effect = PayslipNotFoundError("Bulletin non trouvé")
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/payslips/ps-unknown/edit",
                    json={"payslip_data": {}, "changes_summary": "Résumé"},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 404


class TestPayslipsHistoryRoute:
    """GET /api/payslips/{payslip_id}/history."""

    def test_history_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.get("/api/payslips/ps-1/history")
        assert response.status_code == 401

    def test_history_returns_200_with_auth(self, client: TestClient):
        """Historique (mock) → 200."""
        from app.core.security import get_current_user

        history = [
            {"version": 1, "edited_at": "2024-03-01T10:00:00", "edited_by": "u1", "edited_by_name": "Admin", "changes_summary": "Création", "previous_payslip_data": {}, "previous_pdf_url": None},
        ]
        with patch(
            "app.modules.payslips.api.router.get_payslip_history_for_user",
            return_value=history,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.get("/api/payslips/ps-1/history")
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestPayslipsRestoreRoute:
    """POST /api/payslips/{payslip_id}/restore."""

    def test_restore_returns_401_without_auth(self, client: TestClient):
        """Sans auth → 401."""
        response = client.post(
            "/api/payslips/ps-1/restore",
            json={"version": 1},
        )
        assert response.status_code == 401

    def test_restore_returns_200_with_rh_user(self, client: TestClient):
        """Restauration (mock) → 200."""
        from app.core.security import get_current_user

        result = {
            "payslip": _make_payslip_detail_mock("ps-1"),
            "restored_version": 2,
        }
        with patch(
            "app.modules.payslips.api.router.restore_payslip_for_user",
            return_value=result,
        ):
            app.dependency_overrides[get_current_user] = lambda: _make_rh_user()
            try:
                response = client.post(
                    "/api/payslips/ps-1/restore",
                    json={"version": 2},
                )
            finally:
                app.dependency_overrides.pop(get_current_user, None)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["restored_version"] == 2


class TestPayslipsDebugStorageRoute:
    """GET /api/debug-storage/{employee_id}/{year}/{month}."""

    def test_debug_storage_returns_200_with_mock(self, client: TestClient):
        """Métadonnées storage (mock) → 200."""
        with patch(
            "app.modules.payslips.api.router.get_debug_storage_info",
            return_value={"path": "co/emp/bulletins/Bulletin_03-2024.pdf", "size": 12345},
        ):
            response = client.get("/api/debug-storage/emp-1/2024/3")
        assert response.status_code == 200
        data = response.json()
        assert "path" in data

    def test_debug_storage_returns_404_when_employee_not_found(self, client: TestClient):
        """Employé inexistant → 404."""
        with patch(
            "app.modules.payslips.api.router.get_debug_storage_info"
        ) as mock_get:
            from app.modules.payslips.application.dto import PayslipNotFoundError
            mock_get.side_effect = PayslipNotFoundError("Employé non trouvé")
            response = client.get("/api/debug-storage/emp-unknown/2024/1")
        assert response.status_code == 404
