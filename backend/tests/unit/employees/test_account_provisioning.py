"""Tests unitaires — provisionnement compte collaborateur (recrutement)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application.account_provisioning import (
    provision_collaborator_account,
)

pytestmark = pytest.mark.unit


@patch(
    "app.modules.employees.application.account_provisioning.allocate_collaborator_username",
    return_value="marie.onboard",
)
@patch("app.modules.employees.application.commands._grant_collaborator_company_access")
@patch("app.modules.employees.application.account_provisioning.generate_credentials_pdf")
@patch("app.modules.employees.application.account_provisioning.get_auth_provider")
@patch("app.modules.employees.application.account_provisioning.get_company_reader")
@patch("app.modules.employees.application.account_provisioning.get_storage_provider")
@patch("app.modules.employees.application.account_provisioning._profile_repository")
@patch("app.modules.employees.application.account_provisioning._employee_repository")
def test_provision_collaborator_account_creates_auth_and_pdf(
    mock_repo: MagicMock,
    mock_profile: MagicMock,
    mock_storage_provider: MagicMock,
    mock_company_reader: MagicMock,
    mock_auth_provider: MagicMock,
    mock_generate_pdf: MagicMock,
    mock_grant: MagicMock,
    mock_allocate_username: MagicMock,
) -> None:
    mock_repo.get_by_id.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "first_name": "Marie",
        "last_name": "Onboard",
        "email": "marie.onboard@test.local",
        "job_title": "Dev",
        "username": "marie.onboard",
        "employee_folder_name": "ONBOARD_Marie",
    }
    mock_repo.update.return_value = {}
    auth = MagicMock()
    auth.create_user.return_value = "user-new"
    mock_auth_provider.return_value = auth
    mock_company_reader.return_value.get_company_data.return_value = {
        "company_name": "Test SA"
    }
    mock_generate_pdf.return_value = b"%PDF-1.4"
    storage = MagicMock()
    storage.list_files.return_value = []
    mock_storage_provider.return_value = storage

    result = provision_collaborator_account("emp-1", "company-1", "rh-1")

    assert result["user_id"] == "user-new"
    assert result["generated_password"] is not None
    assert result["credentials_pdf_path"] == "company-1/emp-1/creation_compte.pdf"
    auth.create_user.assert_called_once()
    mock_profile.upsert.assert_called_once()
    mock_repo.update.assert_called_once()
    mock_grant.assert_called_once_with("user-new", "company-1", "rh-1")
    storage.upload.assert_called_once()


@patch("app.modules.employees.application.account_provisioning._employee_repository")
def test_provision_collaborator_account_rejects_dsn_placeholder_email(
    mock_repo: MagicMock,
) -> None:
    mock_repo.get_by_id.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "first_name": "Jean",
        "last_name": "Martin",
        "email": "import.jean.martin.123448@802485169.dsn-import.local",
        "username": "jean.martin",
    }

    with pytest.raises(ValueError, match="email professionnel"):
        provision_collaborator_account("emp-1", "company-1")
