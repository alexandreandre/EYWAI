"""
Tests de câblage (wiring) du module expenses.

Vérifient que l'injection des dépendances et le flux de bout en bout
(router -> service -> commands/queries -> repository / storage) fonctionnent.
"""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.expenses.application.dto import CreateExpenseInput, UpdateExpenseStatusInput
from app.modules.users.schemas.responses import User, CompanyAccess


pytestmark = pytest.mark.integration

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _make_user():
    """Utilisateur de test pour les routes expenses."""
    return User(
        id=TEST_USER_ID,
        email="user@expenses-wiring.com",
        first_name="Wiring",
        last_name="Expenses",
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


class TestExpensesWiringGetUploadUrl:
    """Flux POST /api/expenses/get-upload-url : router -> service -> query -> storage."""

    def test_get_upload_url_flow_uses_service_and_returns_signed_url(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_signed_upload_url.return_value = {
            "path": f"{TEST_USER_ID}/2025-03-15-abc.pdf",
            "signedURL": "https://signed-upload-wiring",
        }

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.api.router._expense_service",
                mock_svc,
            ):
                response = client.post(
                    "/api/expenses/get-upload-url",
                    json={"filename": "facture.pdf"},
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        data = response.json()
        assert data["path"] == f"{TEST_USER_ID}/2025-03-15-abc.pdf"
        assert data["signedURL"] == "https://signed-upload-wiring"
        mock_svc.get_signed_upload_url.assert_called_once_with(
            TEST_USER_ID, "facture.pdf"
        )


class TestExpensesWiringCreateExpense:
    """Flux POST /api/expenses/ : router -> service -> command -> build_create_payload -> repository."""

    def test_create_expense_flow_builds_input_and_calls_service(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        created = {
            "id": "exp-wiring-1",
            "employee_id": TEST_USER_ID,
            "date": "2025-03-15",
            "amount": 80.0,
            "type": "Restaurant",
            "status": "pending",
            "description": "Déjeuner wiring",
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
                        "amount": 80.0,
                        "type": "Restaurant",
                        "description": "Déjeuner wiring",
                    },
                )
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 201
        body = response.json()
        assert body["id"] == "exp-wiring-1"
        assert body["amount"] == 80.0
        assert body["status"] == "pending"
        mock_svc.create_expense.assert_called_once()
        call_input = mock_svc.create_expense.call_args[0][0]
        assert isinstance(call_input, CreateExpenseInput)
        assert call_input.employee_id == TEST_USER_ID
        assert call_input.amount == 80.0
        assert call_input.type == "Restaurant"


class TestExpensesWiringGetMyExpenses:
    """Flux GET /api/expenses/me : router -> service -> query -> repository (+ storage pour URLs)."""

    def test_get_my_expenses_flow_calls_service_with_user_id(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_my_expenses.return_value = [
            {
                "id": "exp-1",
                "created_at": datetime.now().isoformat(),
                "employee_id": TEST_USER_ID,
                "date": "2025-03-15",
                "amount": 25.0,
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
        assert len(data) == 1
        assert data[0]["id"] == "exp-1"
        mock_svc.get_my_expenses.assert_called_once_with(TEST_USER_ID)


class TestExpensesWiringGetAllExpenses:
    """Flux GET /api/expenses/ : router -> service -> query -> repository."""

    def test_get_all_expenses_flow_calls_service_with_list_input(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.get_all_expenses.return_value = [
            {
                "id": "exp-1",
                "created_at": datetime.now().isoformat(),
                "employee_id": TEST_USER_ID,
                "date": "2025-03-15",
                "amount": 25.0,
                "type": "Transport",
                "status": "pending",
                "employee": {
                    "id": TEST_USER_ID,
                    "first_name": "Jean",
                    "last_name": "Dupont",
                },
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
        assert len(data) == 1
        assert data[0]["employee"]["first_name"] == "Jean"
        mock_svc.get_all_expenses.assert_called_once()
        call_input = mock_svc.get_all_expenses.call_args[0][0]
        assert call_input.status is None


class TestExpensesWiringUpdateExpenseStatus:
    """Flux PATCH /api/expenses/{id}/status : router -> service -> command -> repository."""

    def test_update_expense_status_flow_calls_service_with_input(
        self, client: TestClient
    ):
        from app.core.security import get_current_user

        mock_svc = MagicMock()
        mock_svc.update_expense_status.return_value = {
            "id": "exp-123",
            "created_at": datetime.now().isoformat(),
            "employee_id": TEST_USER_ID,
            "date": "2025-03-15",
            "amount": 25.0,
            "type": "Transport",
            "status": "validated",
        }

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
        assert response.json()["status"] == "validated"
        mock_svc.update_expense_status.assert_called_once()
        call_input = mock_svc.update_expense_status.call_args[0][0]
        assert isinstance(call_input, UpdateExpenseStatusInput)
        assert call_input.expense_id == "exp-123"
        assert call_input.status == "validated"


class TestExpensesWiringEndToEndWithApplicationLayer:
    """Flux bout en bout en mockant uniquement la couche infrastructure (repository + storage)."""

    def test_create_then_list_my_expenses_flow(self, client: TestClient):
        """Vérifie que create_expense (command) et get_my_expenses (query) sont bien enchaînés via le service."""
        from app.core.security import get_current_user

        created_row = {
            "id": "exp-e2e-1",
            "employee_id": TEST_USER_ID,
            "date": "2025-03-15",
            "amount": 99.0,
            "type": "Transport",
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        app.dependency_overrides[get_current_user] = lambda: _make_user()
        try:
            with patch(
                "app.modules.expenses.application.commands.ExpenseRepository"
            ) as mock_repo_class:
                mock_repo = MagicMock()
                mock_repo.create.return_value = created_row
                mock_repo.list_by_employee_id.return_value = [created_row]
                mock_repo_class.return_value = mock_repo

                with patch(
                    "app.modules.expenses.application.queries.ExpenseRepository",
                    mock_repo_class,
                ), patch(
                    "app.modules.expenses.application.queries.ExpenseStorageProvider"
                ) as mock_storage_class:
                    mock_storage = MagicMock()
                    mock_storage.create_signed_urls.return_value = []
                    mock_storage_class.return_value = mock_storage

                    create_resp = client.post(
                        "/api/expenses/",
                        json={
                            "date": "2025-03-15",
                            "amount": 99.0,
                            "type": "Transport",
                        },
                    )
                    assert create_resp.status_code == 201
                    assert create_resp.json()["id"] == "exp-e2e-1"

                    list_resp = client.get("/api/expenses/me")
                    assert list_resp.status_code == 200
                    data = list_resp.json()
                    assert len(data) == 1
                    assert data[0]["id"] == "exp-e2e-1"
                    assert data[0]["amount"] == 99.0
        finally:
            app.dependency_overrides.pop(get_current_user, None)
