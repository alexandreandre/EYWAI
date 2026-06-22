"""Tests unitaires — rapprochement import CP."""

from unittest.mock import patch

import pytest

from app.modules.admin_import.application.cp_import import parse_cp_import_files
from tests.unit.admin_import.test_cp_payslip_parser import BOUFRIDA_PAGE

EMPLOYEES = [
    {
        "id": "emp-boufrida",
        "first_name": "Samir",
        "last_name": "BOUFRIDA",
        "email": "",
        "time_tracking_id": None,
        "employee_folder_name": "BOUFRIDA_Samir",
        "coordonnees_bancaires": {},
        "employment_status": "actif",
    },
]


@pytest.fixture
def mock_repo():
    with patch("app.modules.admin_import.application.cp_import.repo") as mock:
        mock.find_company_by_siret.return_value = {
            "id": "co-comitech",
            "company_name": "COMITECH",
            "siret": "49861035100013",
        }
        mock.list_employees_by_company_ids.return_value = {
            "co-comitech": EMPLOYEES,
        }
        yield mock


class TestParseCpImportMatching:
    def test_matches_matricule_from_text_pages(self, mock_repo):
        with patch(
            "app.modules.admin_import.application.cp_import.parse_pdf_file"
        ) as mock_parse, patch(
            "app.modules.admin_import.application.cp_import.get_adjustments_by_employees_year",
            return_value={},
        ), patch(
            "app.modules.admin_import.application.cp_import._compute_current_cp_soldes",
            return_value=(None, None),
        ):
            from app.modules.admin_import.application.cp_payslip_parser import (
                parse_payslip_page_text,
            )

            page = parse_payslip_page_text(BOUFRIDA_PAGE)
            page.source_file = "comitech.pdf"
            page.page_index = 1
            mock_parse.return_value = ([page], [])

            result = parse_cp_import_files([("comitech.pdf", b"%PDF")])
            assert result["summary"]["total"] == 1
            row = result["rows"][0]
            assert row["employee_id"] == "emp-boufrida"
            assert row["company_id"] == "co-comitech"
            assert row["cp_n_solde"] == 11.96

    def test_unknown_siret_is_error(self, mock_repo):
        mock_repo.find_company_by_siret.return_value = None
        with patch(
            "app.modules.admin_import.application.cp_import.parse_pdf_file"
        ) as mock_parse:
            from app.modules.admin_import.application.cp_payslip_parser import (
                parse_payslip_page_text,
            )

            page = parse_payslip_page_text(BOUFRIDA_PAGE)
            page.source_file = "x.pdf"
            page.page_index = 1
            mock_parse.return_value = ([page], [])

            result = parse_cp_import_files([("x.pdf", b"%PDF")])
            row = result["rows"][0]
            assert row["company_id"] is None
            assert row["review_status"] == "error"
