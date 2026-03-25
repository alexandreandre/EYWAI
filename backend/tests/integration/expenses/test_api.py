"""
Tests d'intégration HTTP des routes du module expenses.

Routes : POST /api/expenses/get-upload-url, POST /api/expenses/, GET /api/expenses/me,
GET /api/expenses/, PATCH /api/expenses/{expense_id}/status.
Utilise : client (TestClient), dependency_overrides pour get_current_user,
et mock du service applicatif (_expense_service) pour éviter la DB réelle.

Fixture optionnelle (conftest.py) : expenses_headers — en-têtes avec token Bearer
pour un utilisateur authentifié (employee_id = user.id). Si non définie, les tests
utilisent dependency_overrides[get_current_user] avec un User de test.
"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_user(user_id: str = TEST_USER_ID):
    """Utilisateur de test (employé ou RH) pour les routes expenses."""
    return User(
        id=user_id,
        email="user@expenses-test.com",
        first_name="Test",
        last_name="Expenses",
        is_super_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Test Co",
                role="rh",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestExpensesUnauthenticated:
    """Sans token : toutes les routes protégées renvoient 401."""

    def test_get_upload_url_returns_401_without_auth(self, client: TestClient):
        response = client.post(
            "/api/expenses/get-upload-url",
            json={"filename": "justificatif.pdf"},
        )
        assert response.status_code == 401

    def test_create_expense_returns_401_without_auth(self, client: TestClient):
        response = client.post(
            "/api/expenses/",
            json={
                "date": "2025-03-15",
                "amount": 50.0,
                "type": "Restaurant",
                "description": "Déjeuner",
            },
        )
        assert response.status_code == 401

    def test_get_my_expenses_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/expenses/me")
        assert response.status_code == 401

    def test_get_all_expenses_returns_401_without_auth(self, client: TestClient):
        response = client.get("/api/expenses/")
        assert response.status_code == 401

    def test_update_expense_status_returns_401_without_auth(self, client: TestClient):
        response = client.patch(
            "/api/expenses/exp-123/status",
            json={"status": "validated"},
        )
        assert response.status_code == 401


class TestGetUploadUrl:
    """POST /api/expenses/get-upload-url."""

    def test_get_upload_url_returns_200_with_path_and_signed_url(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_signed_upload_url.return_value = {
            "path": f"{TEST_USER_ID}/2025-03-15-abc123.pdf",
            "signedURL": "https://signed-upload-url",
        }

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.post(
                    "/api/expenses/get-upload-url",
                    json={"filename": "justificatif.pdf"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert "path" in data
        assert "signedURL" in data
        assert data["signedURL"] == "https://signed-upload-url"
        mock_svc.get_signed_upload_url.assert_called_once_with(
            TEST_USER_ID, "justificatif.pdf"
        )

    def test_get_upload_url_invalid_body_returns_422(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            response = client.post(
                "/api/expenses/get-upload-url",
                json={},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422


class TestCreateExpenseReport:
    """POST /api/expenses/."""

    def test_create_expense_returns_201(self, client: TestClient):
        from app.core.security import get_current_user

        created = {
            "id": "exp-new-1",
            "employee_id": TEST_USER_ID,
            "date": "2025-03-15",
            "amount": 75.50,
            "type": "Restaurant",
            "status": "pending",
            "description": "Déjeuner client",
            "receipt_url": None,
            "filename": None,
            "created_at": datetime.now().isoformat(),
        }
        mock_svc = MagicMock()
        mock_svc.create_expense.return_value = created

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.post(
                    "/api/expenses/",
                    json={
                        "date": "2025-03-15",
                        "amount": 75.50,
                        "type": "Restaurant",
                        "description": "Déjeuner client",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "exp-new-1"
        assert data["amount"] == 75.50
        assert data["type"] == "Restaurant"
        assert data["status"] == "pending"
        mock_svc.create_expense.assert_called_once()
        call_input = mock_svc.create_expense.call_args[0][0]
        assert call_input.employee_id == TEST_USER_ID
        assert call_input.amount == 75.50
        assert call_input.type == "Restaurant"

    def test_create_expense_invalid_type_returns_422(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            response = client.post(
                "/api/expenses/",
                json={
                    "date": "2025-03-15",
                    "amount": 50.0,
                    "type": "InvalidType",
                },
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422


class TestGetMyExpenses:
    """GET /api/expenses/me."""

    def test_get_my_expenses_returns_200_and_list(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_my_expenses.return_value = [
            {
                "id": "exp-1",
                "created_at": datetime.now().isoformat(),
                "employee_id": TEST_USER_ID,
                "date": "2025-03-10",
                "amount": 30.0,
                "type": "Transport",
                "status": "pending",
            },
        ]

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.get("/api/expenses/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "exp-1"
        assert data[0]["amount"] == 30.0
        mock_svc.get_my_expenses.assert_called_once_with(TEST_USER_ID)

    def test_get_my_expenses_empty_returns_empty_list(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_my_expenses.return_value = []

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.get("/api/expenses/me")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json() == []


class TestGetAllExpenses:
    """GET /api/expenses/ (liste RH)."""

    def test_get_all_expenses_returns_200_and_list(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_all_expenses.return_value = [
            {
                "id": "exp-1",
                "created_at": datetime.now().isoformat(),
                "employee_id": "emp-1",
                "date": "2025-03-15",
                "amount": 50.0,
                "type": "Restaurant",
                "status": "pending",
                "employee": {"id": "emp-1", "first_name": "Jean", "last_name": "Dupont"},
            },
        ]

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.get("/api/expenses/")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["employee"]["first_name"] == "Jean"
        mock_svc.get_all_expenses.assert_called_once()

    def test_get_all_expenses_with_status_filter(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_all_expenses.return_value = []

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.get("/api/expenses/?status=validated")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        call_input = mock_svc.get_all_expenses.call_args[0][0]
        assert call_input.status == "validated"


class TestUpdateExpenseStatus:
    """PATCH /api/expenses/{expense_id}/status."""

    def test_update_expense_status_validated_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        updated = {
            "id": "exp-123",
            "created_at": datetime.now().isoformat(),
            "employee_id": "emp-1",
            "date": "2025-03-15",
            "amount": 50.0,
            "type": "Restaurant",
            "status": "validated",
        }
        mock_svc = MagicMock()
        mock_svc.update_expense_status.return_value = updated

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.patch(
                    "/api/expenses/exp-123/status",
                    json={"status": "validated"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "validated"
        assert data["id"] == "exp-123"
        mock_svc.update_expense_status.assert_called_once()
        call_input = mock_svc.update_expense_status.call_args[0][0]
        assert call_input.expense_id == "exp-123"
        assert call_input.status == "validated"

    def test_update_expense_status_rejected_returns_200(self, client: TestClient):
        from app.core.security import get_current_user

        updated = {
            "id": "exp-456",
            "created_at": datetime.now().isoformat(),
            "employee_id": "emp-1",
            "date": "2025-03-16",
            "amount": 42.0,
            "type": "Autre",
            "status": "rejected",
        }
        mock_svc = MagicMock()
        mock_svc.update_expense_status.return_value = updated

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.patch(
                    "/api/expenses/exp-456/status",
                    json={"status": "rejected"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["status"] == "rejected"

    def test_update_expense_status_not_found_returns_404(self, client: TestClient):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.update_expense_status.return_value = None

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.patch(
                    "/api/expenses/exp-inexistant/status",
                    json={"status": "validated"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 404
        assert "non trouvée" in response.json().get("detail", "").lower()

    def test_update_expense_status_invalid_body_returns_422(self, client: TestClient):
        from app.core.security import get_current_user

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            response = client.patch(
                "/api/expenses/exp-123/status",
                json={"status": "pending"},
            )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 422
