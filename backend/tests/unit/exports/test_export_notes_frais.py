"""Tests unitaires export notes de frais (format cabinet comptable)."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_notes_frais as module

pytestmark = pytest.mark.unit

SAMPLE_EXPENSE = {
    "id": "exp-12345678-abcd-efgh",
    "employee_id": "emp-1",
    "date": "2025-06-15",
    "amount": 120.0,
    "vat_rate": 20.0,
    "amount_ht": 100.0,
    "vat_amount": 20.0,
    "type": "Restaurant",
    "description": "Déjeuner client",
    "status": "validated",
    "filename": "ticket.pdf",
    "employee_first_name": "Jean",
    "employee_last_name": "Dupont",
    "employee_number": "E001",
}

SAMPLE_EXPENSE_NO_VAT = {
    **SAMPLE_EXPENSE,
    "id": "exp-no-vat-1234",
    "type": "Transport",
    "amount": 50.0,
    "vat_rate": 0.0,
    "amount_ht": 50.0,
    "vat_amount": 0.0,
}


class TestBuildEcritures:
    def test_generates_balanced_entries_with_vat(self):
        ecritures, totals = module.build_ecritures_from_expenses(
            [SAMPLE_EXPENSE], "2025-06"
        )

        assert len(ecritures) == 3
        assert totals["total_ht"] == 100.0
        assert totals["total_tva"] == 20.0
        assert totals["total_ttc"] == 120.0
        assert totals["equilibre"] is True
        assert totals["total_debit"] == totals["total_credit"]

        charge_line = ecritures[0]
        assert charge_line["compte_comptable"] == "625600"
        assert charge_line["debit"] == 100.0
        assert charge_line["credit"] == 0.0

        tva_line = ecritures[1]
        assert tva_line["compte_comptable"] == "445660"
        assert tva_line["debit"] == 20.0

        credit_line = ecritures[2]
        assert credit_line["compte_comptable"] == "421000"
        assert credit_line["credit"] == 120.0

    def test_generates_two_lines_without_vat(self):
        ecritures, totals = module.build_ecritures_from_expenses(
            [SAMPLE_EXPENSE_NO_VAT], "2025-06"
        )

        assert len(ecritures) == 2
        assert ecritures[0]["compte_comptable"] == "625100"
        assert totals["total_tva"] == 0.0
        assert totals["equilibre"] is True

    def test_charge_account_mapping_by_type(self):
        for expense_type, account in module.EXPENSE_TYPE_ACCOUNTS.items():
            expense = {**SAMPLE_EXPENSE, "type": expense_type}
            ecritures, _ = module.build_ecritures_from_expenses([expense], "2025-06")
            assert ecritures[0]["compte_comptable"] == account


class TestCabinetFormats:
    def test_generique_headers(self):
        ecritures, _ = module.build_ecritures_from_expenses([SAMPLE_EXPENSE], "2025-06")
        rows = module._format_cabinet_rows(ecritures, "generique")

        assert list(rows[0].keys()) == module.CABINET_HEADERS["generique"]
        assert rows[0]["Date"] == "2025-06-15"
        assert rows[0]["Période"] == "2025-06"

    def test_quadra_date_format(self):
        ecritures, _ = module.build_ecritures_from_expenses([SAMPLE_EXPENSE], "2025-06")
        rows = module._format_cabinet_rows(ecritures, "quadra")

        assert rows[0]["Date"] == "2025/06/15"
        assert "Référence" not in rows[0]

    @patch.object(module, "get_expense_reports_for_export")
    def test_quadra_csv_uses_semicolon(self, mock_get_expenses):
        mock_get_expenses.return_value = [SAMPLE_EXPENSE]
        content = module.generate_notes_frais_export(
            "company-1",
            "2025-06",
            file_format="csv",
            cabinet_format="quadra",
        )
        text = content.decode("utf-8")
        assert ";" in text.splitlines()[0]
        assert "Journal;Date;Compte" in text.splitlines()[0]

    @patch.object(module, "get_expense_reports_for_export")
    def test_xlsx_starts_with_pk_zip_header(self, mock_get_expenses):
        mock_get_expenses.return_value = [SAMPLE_EXPENSE]
        content = module.generate_notes_frais_export(
            "company-1",
            "2025-06",
            file_format="xlsx",
            cabinet_format="generique",
        )
        assert content[:2] == b"PK"


class TestPreviewNotesFrais:
    @patch.object(module, "get_expense_reports_for_export")
    def test_blocking_anomaly_when_no_expenses(self, mock_get_expenses):
        mock_get_expenses.return_value = []
        preview = module.preview_notes_frais("company-1", "2025-06")

        assert preview["can_generate"] is False
        assert any(a.get("severity") == "blocking" for a in preview["anomalies"])

    @patch.object(module, "get_expense_reports_for_export")
    def test_can_generate_with_validated_expenses(self, mock_get_expenses):
        mock_get_expenses.return_value = [SAMPLE_EXPENSE]
        preview = module.preview_notes_frais("company-1", "2025-06")

        assert preview["can_generate"] is True
        assert preview["employees_count"] == 1
        assert preview["totals"]["total_ttc"] == 120.0
        assert preview["details"]["lines_count"] == 3
