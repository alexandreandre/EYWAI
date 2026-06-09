"""Routes /api/employees/me/* documents : résolution employees.id."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_current_user
from app.main import app
from app.modules.users.schemas.responses import User, CompanyAccess

TEST_USER_ID = "660e8400-e29b-41d4-a716-446655440001"
TEST_EMPLOYEE_ID = "770e8400-e29b-41d4-a716-446655440099"
TEST_COMPANY_ID = "550e8400-e29b-41d4-a716-446655440000"


def _collaborator_user() -> User:
    return User(
        id=TEST_USER_ID,
        email="emp@test.com",
        first_name="Emp",
        last_name="Test",
        is_platform_admin=False,
        is_group_admin=False,
        accessible_companies=[
            CompanyAccess(
                company_id=TEST_COMPANY_ID,
                company_name="Co",
                role="collaborateur",
                is_primary=True,
            ),
        ],
        active_company_id=TEST_COMPANY_ID,
    )


class TestMyEmployeeMeDocumentsResolve:
    def test_get_my_contract_uses_resolved_employee_id(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.employees.api.router_me.resolve_my_employee_id",
                    return_value=TEST_EMPLOYEE_ID,
                ) as mock_resolve,
                patch(
                    "app.modules.employees.api.router_me.queries.get_my_contract_url",
                    return_value="https://signed-contract",
                ) as mock_contract,
                patch(
                    "app.modules.employees.api.router_me.queries.get_my_contract_preview_url",
                    return_value="https://preview-contract",
                ),
            ):
                response = client.get("/api/employees/me/contract")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["url"] == "https://signed-contract"
        mock_resolve.assert_called_once()
        mock_contract.assert_called_once_with(TEST_EMPLOYEE_ID)

    def test_get_my_identity_document_uses_resolved_employee_id(
        self, client: TestClient
    ):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.employees.api.router_me.resolve_my_employee_id",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.employees.api.router_me.queries.get_identity_document_url",
                    return_value="https://signed-id",
                ) as mock_identity,
                patch(
                    "app.modules.employees.api.router_me.queries.get_identity_document_preview_url",
                    return_value="https://preview-id",
                ),
            ):
                response = client.get("/api/employees/me/identity-document")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        mock_identity.assert_called_once_with(TEST_EMPLOYEE_ID)

    def test_get_my_credentials_pdf_uses_resolved_employee_id(
        self, client: TestClient
    ):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.employees.api.router_me.resolve_my_employee_id",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.employees.api.router_me.queries.get_credentials_pdf_url",
                    return_value="https://signed-credentials",
                ) as mock_credentials,
                patch(
                    "app.modules.employees.api.router_me.queries.get_credentials_pdf_preview_url",
                    return_value="https://preview-credentials",
                ),
            ):
                response = client.get("/api/employees/me/credentials-pdf")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert response.json()["url"] == "https://signed-credentials"
        mock_credentials.assert_called_once_with(TEST_EMPLOYEE_ID)

    def test_get_my_published_exit_documents_uses_resolved_employee_id(
        self, client: TestClient
    ):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with (
                patch(
                    "app.modules.employees.api.router_me.resolve_my_employee_id",
                    return_value=TEST_EMPLOYEE_ID,
                ),
                patch(
                    "app.modules.employees.api.router_me.queries.get_my_published_exit_documents",
                    return_value=[{"id": "doc-1", "name": "Certificat", "url": "u"}],
                ) as mock_exit,
            ):
                response = client.get("/api/employees/me/published-exit-documents")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 200
        assert len(response.json()) == 1
        mock_exit.assert_called_once_with(TEST_EMPLOYEE_ID)

    def test_get_my_contract_returns_404_when_unlinked(self, client: TestClient):
        app.dependency_overrides[get_current_user] = lambda: _collaborator_user()
        try:
            with patch(
                "app.modules.employees.api.deps.resolve_employee_id_for_user_account",
                return_value=None,
            ):
                response = client.get("/api/employees/me/contract")
        finally:
            app.dependency_overrides.pop(get_current_user, None)

        assert response.status_code == 404
