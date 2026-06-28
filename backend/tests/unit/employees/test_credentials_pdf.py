"""Tests unitaires — PDF identifiants de connexion (ensure + lookup)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.employees.application.credentials_pdf import (
    CREDENTIALS_FILENAME,
    find_credentials_pdf_path,
    get_credentials_pdf_url,
)

pytestmark = pytest.mark.unit


def test_find_credentials_pdf_path_by_employee_id() -> None:
    storage = MagicMock()
    storage.list_files.return_value = [{"name": CREDENTIALS_FILENAME}]

    path = find_credentials_pdf_path(
        storage,
        "company-1",
        "emp-1",
        "user-9",
    )

    assert path == "company-1/emp-1/creation_compte.pdf"
    storage.list_files.assert_called_once_with("creation_compte", "company-1/emp-1")


def test_find_credentials_pdf_path_fallback_user_id() -> None:
    storage = MagicMock()
    storage.list_files.side_effect = [
        [],
        [{"name": CREDENTIALS_FILENAME}],
    ]

    path = find_credentials_pdf_path(
        storage,
        "company-1",
        "emp-1",
        "user-9",
    )

    assert path == "company-1/user-9/creation_compte.pdf"


@patch("app.modules.employees.application.credentials_pdf.get_storage_provider")
@patch("app.modules.employees.application.credentials_pdf.ensure_credentials_pdf")
def test_get_credentials_pdf_url_returns_signed_url(
    mock_ensure: MagicMock,
    mock_storage_provider: MagicMock,
) -> None:
    mock_ensure.return_value = "company-1/emp-1/creation_compte.pdf"
    storage = MagicMock()
    storage.create_signed_url.return_value = "https://signed.example/pdf"
    mock_storage_provider.return_value = storage

    url = get_credentials_pdf_url("emp-1")

    assert url == "https://signed.example/pdf"
    storage.create_signed_url.assert_called_once_with(
        "creation_compte",
        "company-1/emp-1/creation_compte.pdf",
        expiry_seconds=3600,
        download=True,
    )


def test_find_credentials_pdf_path_legacy_folder_name() -> None:
    storage = MagicMock()
    storage.list_files.side_effect = [
        [],
        [],
        [],
        [{"name": CREDENTIALS_FILENAME}],
    ]

    path = find_credentials_pdf_path(
        storage,
        "company-1",
        "emp-1",
        "user-9",
        "DUPONT_Jean",
    )

    assert path == "DUPONT_Jean/creation_compte.pdf"


@patch("app.modules.employees.application.credentials_pdf.generate_credentials_pdf")
@patch("app.modules.employees.application.credentials_pdf.get_auth_provider")
@patch("app.modules.employees.application.credentials_pdf.get_company_reader")
@patch("app.modules.employees.application.credentials_pdf.get_storage_provider")
@patch("app.modules.employees.application.credentials_pdf.get_employee_company_id")
@patch("app.modules.employees.application.credentials_pdf._employee_repository")
def test_ensure_credentials_pdf_generates_when_auth_user_missing(
    mock_repo: MagicMock,
    mock_company_id: MagicMock,
    mock_storage_provider: MagicMock,
    mock_company_reader: MagicMock,
    mock_auth_provider: MagicMock,
    mock_generate_pdf: MagicMock,
) -> None:
    from app.modules.employees.application.credentials_pdf import ensure_credentials_pdf

    mock_company_id.return_value = "company-1"
    mock_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "user_id": "user-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "username": "jean.dupont",
        "email": "jean.dupont@example.com",
    }
    mock_repo.get_by_id.return_value = mock_repo.get_by_id_only.return_value
    storage = MagicMock()
    storage.list_files.return_value = []
    mock_storage_provider.return_value = storage
    mock_company_reader.return_value.get_company_data.return_value = {"company_name": "Test SA"}
    mock_generate_pdf.return_value = b"%PDF-1.4"
    auth = MagicMock()
    auth.update_user_password.side_effect = RuntimeError("User not found")
    mock_auth_provider.return_value = auth

    path = ensure_credentials_pdf("emp-1")

    assert path == "company-1/emp-1/creation_compte.pdf"
    storage.upload.assert_called_once()
    mock_generate_pdf.assert_called_once()
    assert "contactez les RH" in mock_generate_pdf.call_args.kwargs["password"]


@patch("app.modules.employees.application.credentials_pdf.store_credentials_pdf_for_employee")
@patch("app.modules.employees.application.credentials_pdf.find_credentials_pdf_path")
@patch("app.modules.employees.application.credentials_pdf.get_storage_provider")
@patch("app.modules.employees.application.credentials_pdf.get_employee_company_id")
@patch("app.modules.employees.application.credentials_pdf._employee_repository")
def test_ensure_credentials_pdf_skips_provision_for_dsn_placeholder_email(
    mock_repo: MagicMock,
    mock_company_id: MagicMock,
    mock_storage_provider: MagicMock,
    mock_find_path: MagicMock,
    mock_store_pdf: MagicMock,
) -> None:
    from app.modules.employees.application.credentials_pdf import (
        CREDENTIALS_PASSWORD_UNAVAILABLE,
        ensure_credentials_pdf,
    )

    mock_company_id.return_value = "company-1"
    mock_repo.get_by_id_only.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "user_id": None,
        "first_name": "Jean",
        "last_name": "Martin",
        "username": "jean.martin",
        "email": "import.jean.martin.123448@802485169.dsn-import.local",
    }
    mock_find_path.return_value = None
    mock_store_pdf.return_value = "company-1/emp-1/creation_compte.pdf"

    with patch(
        "app.modules.employees.application.account_provisioning.provision_collaborator_account"
    ) as mock_provision:
        path = ensure_credentials_pdf("emp-1")

    assert path == "company-1/emp-1/creation_compte.pdf"
    mock_provision.assert_not_called()
    mock_store_pdf.assert_called_once_with(
        "emp-1",
        "company-1",
        password=CREDENTIALS_PASSWORD_UNAVAILABLE,
    )


@patch("app.modules.employees.application.credentials_pdf.generate_credentials_pdf")
@patch("app.modules.employees.application.credentials_pdf.get_company_reader")
@patch("app.modules.employees.application.credentials_pdf.get_storage_provider")
@patch("app.modules.employees.application.credentials_pdf._employee_repository")
def test_store_credentials_pdf_for_employee_uploads_canonical_path(
    mock_repo: MagicMock,
    mock_storage_provider: MagicMock,
    mock_company_reader: MagicMock,
    mock_generate_pdf: MagicMock,
) -> None:
    from app.modules.employees.application.credentials_pdf import (
        store_credentials_pdf_for_employee,
    )

    mock_repo.get_by_id.return_value = {
        "id": "emp-1",
        "company_id": "company-1",
        "first_name": "Jean",
        "last_name": "Dupont",
        "username": "jean.dupont",
    }
    storage = MagicMock()
    mock_storage_provider.return_value = storage
    mock_company_reader.return_value.get_company_data.return_value = {"company_name": "Test SA"}
    mock_generate_pdf.return_value = b"%PDF-1.4"

    path = store_credentials_pdf_for_employee(
        "emp-1",
        "company-1",
        password="TempPass123!",
        username="jean.dupont",
    )

    assert path == "company-1/emp-1/creation_compte.pdf"
    storage.upload.assert_called_once_with(
        "creation_compte",
        "company-1/emp-1/creation_compte.pdf",
        b"%PDF-1.4",
        "application/pdf",
    )
