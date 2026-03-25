"""
Tests unitaires des queries expenses (application/queries.py).

Chaque query est testée avec repository et storage mockés (patch ExpenseRepository,
ExpenseStorageProvider).
"""

import re
from unittest.mock import MagicMock, patch

from app.modules.expenses.application.queries import (
    get_my_expenses,
    get_all_expenses,
    get_signed_upload_url,
)


class TestGetMyExpenses:
    """Query get_my_expenses."""

    def test_get_my_expenses_returns_list_from_repo(self):
        mock_repo = MagicMock()
        mock_repo.list_by_employee_id.return_value = [
            {
                "id": "exp-1",
                "employee_id": "emp-001",
                "date": "2025-03-15",
                "amount": 25.0,
                "type": "Restaurant",
                "status": "pending",
                "receipt_url": None,
            },
        ]
        with patch(
            "app.modules.expenses.application.queries.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = get_my_expenses("emp-001")

        mock_repo.list_by_employee_id.assert_called_once_with("emp-001")
        assert len(result) == 1
        assert result[0]["id"] == "exp-1"
        assert result[0]["amount"] == 25.0

    def test_get_my_expenses_empty_returns_empty_list(self):
        mock_repo = MagicMock()
        mock_repo.list_by_employee_id.return_value = []

        with patch(
            "app.modules.expenses.application.queries.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = get_my_expenses("emp-empty")

        assert result == []

    def test_get_my_expenses_signs_receipt_urls_via_storage(self):
        mock_repo = MagicMock()
        mock_repo.list_by_employee_id.return_value = [
            {
                "id": "exp-1",
                "employee_id": "emp-001",
                "receipt_url": "emp-001/file1.pdf",
            },
            {"id": "exp-2", "employee_id": "emp-001", "receipt_url": None},
        ]
        mock_storage = MagicMock()
        mock_storage.create_signed_urls.return_value = [
            {"signedURL": "https://signed-url-1"},
        ]

        with (
            patch(
                "app.modules.expenses.application.queries.ExpenseRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.expenses.application.queries.ExpenseStorageProvider",
                return_value=mock_storage,
            ),
        ):
            result = get_my_expenses("emp-001")

        mock_storage.create_signed_urls.assert_called_once_with(
            ["emp-001/file1.pdf"],
            3600,
        )
        assert result[0]["receipt_url"] == "https://signed-url-1"
        assert result[1]["receipt_url"] is None

    def test_get_my_expenses_uses_signedUrl_if_present(self):
        mock_repo = MagicMock()
        mock_repo.list_by_employee_id.return_value = [
            {"id": "exp-1", "receipt_url": "path/to/file.pdf"},
        ]
        mock_storage = MagicMock()
        mock_storage.create_signed_urls.return_value = [
            {"signedUrl": "https://signed-url-alt"},
        ]

        with (
            patch(
                "app.modules.expenses.application.queries.ExpenseRepository",
                return_value=mock_repo,
            ),
            patch(
                "app.modules.expenses.application.queries.ExpenseStorageProvider",
                return_value=mock_storage,
            ),
        ):
            result = get_my_expenses("emp-001")

        assert result[0]["receipt_url"] == "https://signed-url-alt"


class TestGetAllExpenses:
    """Query get_all_expenses."""

    def test_get_all_expenses_calls_repo_list_all(self):
        mock_repo = MagicMock()
        mock_repo.list_all.return_value = [
            {
                "id": "exp-1",
                "employee_id": "emp-1",
                "status": "pending",
                "employee": {},
            },
        ]

        with patch(
            "app.modules.expenses.application.queries.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = get_all_expenses()

        mock_repo.list_all.assert_called_once_with(None)
        assert len(result) == 1
        assert result[0]["id"] == "exp-1"

    def test_get_all_expenses_with_status_filter(self):
        mock_repo = MagicMock()
        mock_repo.list_all.return_value = [
            {"id": "exp-2", "status": "validated", "employee": {}},
        ]

        with patch(
            "app.modules.expenses.application.queries.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = get_all_expenses(status="validated")

        mock_repo.list_all.assert_called_once_with("validated")
        assert result[0]["status"] == "validated"

    def test_get_all_expenses_empty(self):
        mock_repo = MagicMock()
        mock_repo.list_all.return_value = []

        with patch(
            "app.modules.expenses.application.queries.ExpenseRepository",
            return_value=mock_repo,
        ):
            result = get_all_expenses(status="rejected")

        assert result == []


class TestGetSignedUploadUrl:
    """Query get_signed_upload_url."""

    def test_get_signed_upload_url_returns_path_and_signed_url(self):
        mock_storage = MagicMock()
        mock_storage.create_signed_upload_url.return_value = {
            "signedUrl": "https://upload-signed-url",
        }

        with patch(
            "app.modules.expenses.application.queries.ExpenseStorageProvider",
            return_value=mock_storage,
        ):
            result = get_signed_upload_url("emp-001", "justificatif.pdf")

        assert "path" in result
        assert result["path"].startswith("emp-001/")
        assert re.search(r"emp-001/\d{4}-", result["path"])
        assert result["path"].endswith(".pdf")
        assert result["signedURL"] == "https://upload-signed-url"
        mock_storage.create_signed_upload_url.assert_called_once()
        call_path = mock_storage.create_signed_upload_url.call_args[0][0]
        assert call_path.startswith("emp-001/")
        assert call_path.endswith(".pdf")

    def test_get_signed_upload_url_preserves_extension(self):
        mock_storage = MagicMock()
        mock_storage.create_signed_upload_url.return_value = {"signedUrl": "https://x"}

        with patch(
            "app.modules.expenses.application.queries.ExpenseStorageProvider",
            return_value=mock_storage,
        ):
            result = get_signed_upload_url("emp-002", "image.png")

        assert result["path"].endswith(".png")
