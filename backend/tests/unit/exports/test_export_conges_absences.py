"""Tests unitaires export congés / absences."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_conges_absences as module

pytestmark = pytest.mark.unit

SAMPLE_ABSENCE = {
    "id": "abs-1",
    "employee_id": "emp-1",
    "type": "conge_paye",
    "type_label": "Congé payé",
    "status": "validated",
    "days_count": 2,
    "days_in_period": ["2025-06-10", "2025-06-11"],
    "employee_first_name": "Marie",
    "employee_last_name": "Martin",
}


class TestPreviewCongesAbsences:
    @patch.object(module, "get_absences_for_export")
    def test_blocking_when_no_absences(self, mock_get):
        mock_get.return_value = []
        preview = module.preview_conges_absences("company-1", "2025-06")

        assert preview["can_generate"] is False
        assert any(a.get("severity") == "blocking" for a in preview["anomalies"])

    @patch.object(module, "get_absences_for_export")
    def test_can_generate_with_validated_absences(self, mock_get):
        mock_get.return_value = [SAMPLE_ABSENCE]
        preview = module.preview_conges_absences("company-1", "2025-06")

        assert preview["can_generate"] is True
        assert preview["employees_count"] == 1
        assert preview["details"]["total_days"] == 2


class TestGenerateCongesAbsences:
    @patch.object(module, "get_absences_for_export")
    def test_xlsx_starts_with_pk_zip_header(self, mock_get):
        mock_get.return_value = [SAMPLE_ABSENCE]
        content = module.generate_conges_absences_export(
            "company-1", "2025-06", file_format="xlsx"
        )
        assert content[:2] == b"PK"
