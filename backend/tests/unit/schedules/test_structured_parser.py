"""Tests parseur tabulaire import pointages."""

import io

from app.modules.schedules.application.timesheet_import.structured_parser import (
    detect_column_mapping,
    parse_tabular_file,
)


CSV_SAMPLE = """matricule;nom;date;heures
196;ADAM YOUSSEF;01/05/2026;7.5
196;ADAM YOUSSEF;02/05/2026;8:00
270;DURAND Sophie;03/05/2026;7h30
"""


class TestStructuredParser:
    def test_detect_column_mapping(self):
        headers = ["matricule", "nom", "date", "heures"]
        mapping = detect_column_mapping(headers)
        assert mapping["matricule"] == "matricule"
        assert mapping["date"] == "date"
        assert mapping["hours"] == "heures"

    def test_parse_csv_semicolon(self):
        result = parse_tabular_file(
            CSV_SAMPLE.encode("utf-8"),
            "pointages.csv",
            target_year=2026,
            target_month=5,
        )
        assert result.confidence >= 0.65
        assert len(result.rows) == 3
        assert result.rows[0].matricule == "196"
        assert result.rows[0].heures == 7.5

    def test_parse_hours_formats(self):
        from app.modules.schedules.application.timesheet_import.structured_parser import (
            _parse_hours,
        )

        assert _parse_hours("7:30") == 7.5
        assert _parse_hours("7h30") == 7.5
        assert _parse_hours("7,5", decimal_separator=",") == 7.5
