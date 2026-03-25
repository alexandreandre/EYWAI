"""
Tests unitaires du service applicatif exports.

Le service orchestre preview, history, download et generate ; les dépendances (queries, commands,
providers, storage) sont mockées.
"""
from unittest.mock import patch

import pytest

from app.modules.exports.application import service as export_service
from app.modules.exports.schemas import (
    ExportPreviewRequest,
    ExportPreviewResponse,
    ExportGenerateRequest,
    ExportHistoryResponse,
    ExportTotals,
)


pytestmark = pytest.mark.unit


class TestServicePreviewExport:
    """Service.preview_export : délégation à queries."""

    def test_delegates_to_queries_and_returns_response(self):
        """preview_export délègue à queries.preview_export et retourne le résultat."""
        req = ExportPreviewRequest(export_type="journal_paie", period="2025-01")
        expected = ExportPreviewResponse(
            export_type="journal_paie",
            period="2025-01",
            employees_count=2,
            totals=ExportTotals(employees_count=2),
            anomalies=[],
            warnings=[],
            can_generate=True,
        )
        with patch.object(export_service.queries, "preview_export", return_value=expected) as mock_q:
            result = export_service.preview_export("company-1", req)
            mock_q.assert_called_once_with("company-1", req)
            assert result == expected


class TestServiceGetExportHistory:
    """Service.get_export_history : délégation à queries."""

    def test_delegates_to_queries(self):
        """get_export_history délègue à queries.get_export_history."""
        expected = ExportHistoryResponse(exports=[], total=0)
        with patch.object(export_service.queries, "get_export_history", return_value=expected) as mock_q:
            result = export_service.get_export_history("company-1", "dsn_mensuelle", "2025-01")
            mock_q.assert_called_once_with("company-1", "dsn_mensuelle", "2025-01")
            assert result == expected


class TestServiceGetExportDownloadUrl:
    """Service.get_export_download_url : délégation à queries."""

    def test_delegates_to_queries_and_returns_url(self):
        """get_export_download_url délègue à queries.get_export_for_download."""
        with patch.object(
            export_service.queries,
            "get_export_for_download",
            return_value="https://signed.url/file.xlsx",
        ) as mock_q:
            url = export_service.get_export_download_url("company-1", "exp-123")
            mock_q.assert_called_once_with("company-1", "exp-123")
            assert url == "https://signed.url/file.xlsx"


class TestServiceGenerateExport:
    """Service.generate_export : type non supporté et délégation métier."""

    def test_unsupported_export_type_raises_value_error(self):
        """Type non supporté pour generate lève ValueError."""
        req = ExportGenerateRequest(export_type="journal_paie", period="2025-01")
        with patch.object(
            export_service.domain_rules,
            "is_supported_export_type_for_generate",
            return_value=False,
        ):
            with pytest.raises(ValueError) as exc_info:
                export_service.generate_export("company-1", "user-1", req)
            assert "non implémenté" in str(exc_info.value)

    def test_generate_journal_paie_returns_response_with_export_id(self):
        """generate_export pour journal_paie appelle providers, storage, commands et retourne ExportGenerateResponse."""
        req = ExportGenerateRequest(
            export_type="journal_paie",
            period="2025-01",
            format="xlsx",
        )
        file_content = b"xlsx-content"
        with patch.object(
            export_service.domain_rules,
            "is_supported_export_type_for_generate",
            return_value=True,
        ):
            with patch.object(
                export_service,
                "get_user_display_name",
                return_value="Jean Dupont",
            ):
                with patch.object(
                    export_service.providers,
                    "generate_journal_paie_export",
                    return_value=file_content,
                ):
                    with patch.object(
                        export_service.providers,
                        "get_journal_paie_data",
                        return_value=([], {"employees_count": 3, "total_brut": 10000.0}),
                    ):
                        with patch.object(
                            export_service,
                            "upload_export_file",
                            return_value="exports/company-1/journal_paie/file.xlsx",
                        ):
                            with patch.object(
                                export_service,
                                "create_signed_url",
                                return_value="https://signed.url/file.xlsx",
                            ):
                                with patch.object(
                                    export_service.commands,
                                    "record_export_history",
                                    return_value="export-uuid-xyz",
                                ):
                                    result = export_service.generate_export("company-1", "user-1", req)

        assert result.export_id == "export-uuid-xyz"
        assert result.export_type == "journal_paie"
        assert result.period == "2025-01"
        assert result.status == "generated"
        assert len(result.files) == 1
        assert result.files[0].format == "xlsx"
        assert result.report.generated_by == "Jean Dupont"
        assert result.report.employees_count == 3
