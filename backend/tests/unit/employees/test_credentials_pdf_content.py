"""Tests unitaires — contenu PDF identifiants (proxy aperçu)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@patch("app.modules.employees.application.queries.get_storage_provider")
@patch("app.modules.employees.application.credentials_pdf.ensure_credentials_pdf")
@patch("app.modules.employees.application.queries._employee_repository")
def test_get_credentials_pdf_content_returns_bytes(
    mock_repo: MagicMock,
    mock_ensure: MagicMock,
    mock_storage_provider: MagicMock,
) -> None:
    from app.modules.employees.application.queries import get_credentials_pdf_content

    mock_ensure.return_value = "company-1/emp-1/creation_compte.pdf"
    mock_repo.get_by_id_only.return_value = {
        "first_name": "Tristan",
        "last_name": "AGOUMBI OGANDAGA",
    }
    storage = MagicMock()
    storage.download.return_value = b"%PDF-1.4 test"
    mock_storage_provider.return_value = storage

    content, filename = get_credentials_pdf_content("emp-1")

    assert content.startswith(b"%PDF")
    assert filename == "Compte_Tristan_AGOUMBI_OGANDAGA.pdf"
    storage.download.assert_called_once_with("creation_compte", "company-1/emp-1/creation_compte.pdf")


@patch("app.modules.employees.application.credentials_pdf.ensure_credentials_pdf")
def test_get_credentials_pdf_content_missing(mock_ensure: MagicMock) -> None:
    from app.modules.employees.application.queries import get_credentials_pdf_content

    mock_ensure.return_value = None

    with pytest.raises(LookupError, match="introuvable"):
        get_credentials_pdf_content("emp-1")
