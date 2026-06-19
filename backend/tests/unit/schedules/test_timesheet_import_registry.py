"""Tests registre parseurs import pointages."""

from app.modules.schedules.application.timesheet_import.registry import (
    detect_source_type,
    parse_document,
)

CSV = b"matricule;date;heures\n196;01/05/2026;8\n"


class TestParserRegistry:
    def test_detect_source_type(self):
        assert detect_source_type("relevé.pdf") == "document_pdf"
        assert detect_source_type("export.csv") == "csv"
        assert detect_source_type("data.xlsx") == "xlsx"

    def test_routes_csv_to_tabular(self):
        attempt = parse_document(
            CSV,
            "export.csv",
            company_id="c1",
            year=2026,
            month=5,
            skip_llm=True,
        )
        assert attempt.parser_key == "tabular_generic"
        assert attempt.confidence > 0
