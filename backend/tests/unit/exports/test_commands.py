"""
Tests unitaires des commandes applicatives exports.

Chaque commande est testée avec le repository (insert_export_record) mocké.
"""

from unittest.mock import patch

import pytest

from app.modules.exports.application.commands import record_export_history
from app.modules.exports.application.dto import ExportRecordForInsert


pytestmark = pytest.mark.unit


class TestRecordExportHistory:
    """Commande record_export_history : enregistrement dans exports_history."""

    def test_returns_export_id_when_insert_succeeds(self):
        """Quand insert_export_record retourne un id, record_export_history le retourne."""
        record: ExportRecordForInsert = {
            "company_id": "company-1",
            "export_type": "journal_paie",
            "period": "2025-01",
            "parameters": {},
            "file_paths": ["exports/company-1/journal_paie/file.xlsx"],
            "report": {"employees_count": 5},
            "status": "generated",
            "generated_by": "user-1",
        }
        with patch(
            "app.modules.exports.application.commands.repository.insert_export_record",
            return_value="export-uuid-123",
        ) as mock_insert:
            result = record_export_history(record)
            mock_insert.assert_called_once_with(record)
            assert result == "export-uuid-123"

    def test_returns_empty_string_when_insert_returns_none(self):
        """Quand insert_export_record retourne None, record_export_history retourne chaîne vide."""
        record: ExportRecordForInsert = {
            "company_id": "company-1",
            "export_type": "dsn_mensuelle",
            "period": "2025-02",
            "parameters": {"dsn_type": "dsn_mensuelle_normale"},
            "file_paths": [],
            "report": {},
            "status": "generated",
            "generated_by": "user-2",
        }
        with patch(
            "app.modules.exports.application.commands.repository.insert_export_record",
            return_value=None,
        ) as mock_insert:
            result = record_export_history(record)
            mock_insert.assert_called_once_with(record)
            assert result == ""

    def test_passes_full_record_to_repository(self):
        """Le record complet (file_paths, report, etc.) est transmis au repository."""
        record: ExportRecordForInsert = {
            "company_id": "co-1",
            "export_type": "virement_salaires",
            "period": "2025-03",
            "parameters": {
                "execution_date": "2025-03-15",
                "payment_label": "Salaire mars",
            },
            "file_paths": ["path/export.csv", "path/bank.csv"],
            "report": {"employees_count": 10, "totals": {"total_net_a_payer": 25000.0}},
            "status": "generated",
            "generated_by": "user-rh",
        }
        with patch(
            "app.modules.exports.application.commands.repository.insert_export_record",
            return_value="exp-456",
        ) as mock_insert:
            record_export_history(record)
            call_arg = mock_insert.call_args[0][0]
            assert call_arg["company_id"] == "co-1"
            assert call_arg["export_type"] == "virement_salaires"
            assert call_arg["file_paths"] == ["path/export.csv", "path/bank.csv"]
            assert call_arg["report"]["employees_count"] == 10
            assert call_arg["generated_by"] == "user-rh"
