"""Tests lecture Excel tolérante."""

import pytest

from app.shared.utils.xlsx_safe import iter_sheet_rows, read_xlsx_raw_rows


class TestXlsxSafe:
    def test_reads_simple_xlsx(self):
        pytest.importorskip("openpyxl")
        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["Matricule", "Jour", "Nom", "Tot H Poin"])
        ws.append(["000005", "08/06/2026", "Francine BOURMAULT", "7,05"])
        buf = BytesIO()
        wb.save(buf)

        rows = iter_sheet_rows(buf.getvalue())
        assert rows[0][:4] == ["Matricule", "Jour", "Nom", "Tot H Poin"]
        assert rows[1][0] == "000005"
        assert rows[1][3] in ("7,05", 7.05, "7.05")

    def test_zip_fallback_reads_without_openpyxl_styles(self):
        pytest.importorskip("openpyxl")
        from io import BytesIO

        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.append(["matricule", "date", "heures"])
        ws.append(["196", "01/05/2026", "7,5"])
        buf = BytesIO()
        wb.save(buf)
        content = buf.getvalue()

        rows = read_xlsx_raw_rows(content)
        assert rows[0] == ["matricule", "date", "heures"]
        assert rows[1][0] == "196"
