"""Tests unitaires — détection colonnes Excel RIB."""

from io import BytesIO

import pytest

from app.modules.admin_import.application.rib_excel import (
    detect_rib_column_mapping,
    find_header_row_index,
    read_tabular_file,
)


class TestDetectRibColumnMapping:
    def test_detects_rib_and_identity_columns(self):
        headers = ["Nom", "Prénom", "Matricule", "RIB", "Email"]
        mapping = detect_rib_column_mapping(headers)
        assert mapping["rib"] == "RIB"
        assert mapping["last_name"] == "Nom"
        assert mapping["first_name"] == "Prénom"
        assert mapping["matricule"] == "Matricule"
        assert mapping["email"] == "Email"

    def test_detects_iban_alias(self):
        mapping = detect_rib_column_mapping(["Salarié", "IBAN"])
        assert mapping["rib"] == "IBAN"
        assert mapping["full_name"] == "Salarié"


class TestFindHeaderRowIndex:
    def test_finds_header_on_third_row(self):
        raw = [
            ["Export RIB salariés"],
            ["Entreprise Demo", "", ""],
            ["Nom", "Prénom", "RIB"],
            ["Martin", "Paul", "FR1420041010050500013M02606"],
        ]
        assert find_header_row_index(raw) == 2

    def test_ignores_title_containing_rib_word(self):
        raw = [
            ["Export RIB salariés janvier"],
            ["Nom", "Prénom", "RIB"],
            ["Martin", "Paul", "FR1420041010050500013M02606"],
        ]
        assert find_header_row_index(raw) == 1


class TestReadTabularFile:
    def test_reads_csv(self):
        content = (
            "Nom,Prénom,RIB\n"
            "Martin,Paul,FR1420041010050500013M02606\n"
        ).encode("utf-8")
        sheet = read_tabular_file(content, "ribs.csv")
        assert sheet.headers == ["Nom", "Prénom", "RIB"]
        assert len(sheet.rows) == 1
        assert sheet.rows[0]["Nom"] == "Martin"

    def test_reads_csv_with_preamble(self):
        content = (
            "Export RIB\n"
            "Société Test\n"
            "Nom;Prénom;RIB\n"
            "Martin;Paul;FR1420041010050500013M02606\n"
        ).encode("utf-8")
        sheet = read_tabular_file(content, "ribs.csv")
        assert sheet.headers == ["Nom", "Prénom", "RIB"]
        assert sheet.header_row_index == 3
        assert len(sheet.rows) == 1

    def test_reads_xlsx_with_header_on_third_row(self):
        pytest.importorskip("openpyxl")
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Export RIB salariés"
        ws["A2"] = "Entreprise XYZ"
        ws["A3"] = "Nom"
        ws["B3"] = "Prénom"
        ws["C3"] = "RIB"
        ws["A4"] = "Martin"
        ws["B4"] = "Paul"
        ws["C4"] = "FR1420041010050500013M02606"
        buf = BytesIO()
        wb.save(buf)

        sheet = read_tabular_file(buf.getvalue(), "ribs.xlsx")
        assert sheet.headers == ["Nom", "Prénom", "RIB"]
        assert sheet.header_row_index == 3
        assert len(sheet.rows) == 1
        assert sheet.rows[0]["Nom"] == "Martin"
