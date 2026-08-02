"""Tests parseur tabulaire import pointages."""

from datetime import date
from pathlib import Path

from app.modules.schedules.application.timesheet_import.structured_parser import (
    detect_column_mapping,
    filter_tabular_rows_to_period,
    find_header_row_index,
    is_mapping_sufficient,
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

    def test_detect_lewis_headers(self):
        headers = [
            "matricule",
            "Jour",
            "Nom",
            "Entrée 1.",
            "Sortie 3.",
            "Tot H Poin",
            "Code Horai",
        ]
        mapping = detect_column_mapping(headers)
        assert mapping["matricule"] == "matricule"
        assert mapping["date"] == "Jour"
        assert mapping["entry_1"] == "Entrée 1."
        assert mapping["exit_last"] == "Sortie 3."
        assert mapping["hours"] == "Tot H Poin"
        assert mapping["shift_code"] == "Code Horai"
        assert is_mapping_sufficient(mapping)

    def test_is_mapping_sufficient(self):
        assert is_mapping_sufficient({"date": "Jour", "hours": "Heures"})
        assert is_mapping_sufficient(
            {"date": "Jour", "entry_1": "Entrée 1", "exit_last": "Sortie 3"}
        )
        assert not is_mapping_sufficient({"matricule": "Mat"})
        assert not is_mapping_sufficient({"date": "Jour"})

    def test_find_header_row_with_preamble(self):
        raw = [
            ["Export pointages hebdomadaires"],
            ["Société Demo"],
            ["matricule", "Jour", "Nom", "Heures"],
            ["196", "01/05/2026", "ADAM YOUSSEF", "7.5"],
        ]
        assert find_header_row_index(raw) == 2

    def test_parse_csv_with_preamble(self):
        content = (
            "Export pointages\n"
            "Société Test\n"
            "matricule;nom;date;heures\n"
            "196;ADAM YOUSSEF;01/05/2026;7.5\n"
        ).encode("utf-8")
        result = parse_tabular_file(
            content,
            "pointages.csv",
            target_year=2026,
            target_month=5,
        )
        assert len(result.rows) == 1
        assert result.rows[0].matricule == "196"
        assert result.rows[0].heures == 7.5

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

    def test_parse_lewis_cegid_format_french_decimals(self):
        csv = (
            "Matricule;Jour;Nom;Cod Sectio;Entrée 1.;Sortie 1.;Entrée 2.;Sortie 2.;"
            "Entrée 3.;Sortie 3.;Tot H Poin;Hr Théoriq;Code Horai\n"
            "000005;08/06/2026;Camille DELAUNAY;MONT;800;1000;1015;1230;1300;1548;7,05;7,75;A\n"
            "000151;09/06/2026;Olivier MARCHESI;POIN;740;1000;1015;1230;1300;1630;8,08;7,75;A\n"
        )
        result = parse_tabular_file(
            csv.encode("utf-8"),
            "pointages.csv",
            target_year=2026,
            target_month=6,
        )
        assert is_mapping_sufficient(result.column_mapping)
        assert len(result.rows) == 2
        assert result.rows[0].heures == 7.05
        assert result.rows[0].matricule == "000005"
        assert result.rows[0].shift_code == "A"

    def test_parse_lewis_when_ui_month_wrong(self):
        csv = (
            "Matricule;Jour;Nom;Cod Sectio;Entrée 1.;Sortie 1.;Entrée 2.;Sortie 2.;"
            "Entrée 3.;Sortie 3.;Tot H Poin;Hr Théoriq;Code Horai\n"
            "000005;08/06/2026;Camille DELAUNAY;MONT;800;1000;1015;1230;1300;1548;7,05;7,75;A\n"
            "000151;09/06/2026;Olivier MARCHESI;POIN;740;1000;1015;1230;1300;1630;8,08;7,75;A\n"
        )
        parsed = parse_tabular_file(
            csv.encode("utf-8"),
            "pointages.csv",
            target_year=2026,
            target_month=5,
            options={"skip_period_filter": True},
        )
        assert len(parsed.rows) == 2
        filtered = filter_tabular_rows_to_period(
            parsed.rows,
            start=date(2026, 6, 8),
            end=date(2026, 6, 11),
            eff_year=2026,
            eff_month=6,
        )
        assert len(filtered) == 2
        assert filtered[0].jour == 8

    def test_parse_lewis_punch_pairs_csv(self):
        sample_path = (
            Path(__file__).resolve().parents[2]
            / "fixtures"
            / "timesheets"
            / "lewis_june2026_sample.csv"
        )
        content = sample_path.read_bytes()
        result = parse_tabular_file(
            content,
            "lewis_june2026_sample.csv",
            target_year=2026,
            target_month=6,
        )
        assert result.confidence >= 0.75
        assert len(result.rows) >= 5
        assert result.column_mapping.get("entry_1")
        assert result.column_mapping.get("exit_last")
        premier = next(r for r in result.rows if r.jour == 8 and r.matricule == "000005")
        assert premier.entry_raw == 800 or str(premier.entry_raw) == "800"
        assert premier.shift_code == "A"
