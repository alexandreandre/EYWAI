"""Tests unitaires — import dates d'ancienneté."""

from unittest.mock import patch

import pytest

from app.modules.admin_import.application.seniority_excel import (
    detect_seniority_column_mapping,
    parse_seniority_date_cell,
)
from app.modules.admin_import.application.seniority_import import (
    commit_seniority_import,
    parse_seniority_import_file,
)
from app.modules.admin_import.schemas.requests import (
    SeniorityImportCommitBody,
    SeniorityImportCommitRow,
)


EMPLOYEES = [
    {
        "id": "emp-1",
        "first_name": "Francine",
        "last_name": "BOURMAULT",
        "email": "f@example.com",
        "time_tracking_id": None,
        "employee_folder_name": "BOURMAULT_Francine",
        "employment_status": "actif",
        "hire_date": "2020-01-01",
        "seniority_reference_date": None,
        "statut": "Non cadre",
        "classification_conventionnelle": {"classe_emploi": 5},
    },
    {
        "id": "emp-2",
        "first_name": "Marc",
        "last_name": "CLEMENT",
        "email": "m@example.com",
        "time_tracking_id": None,
        "employee_folder_name": "CLEMENT_Marc",
        "employment_status": "actif",
        "hire_date": "2013-06-03",
        "seniority_reference_date": "2013-06-03",
        "statut": "Non cadre",
        "classification_conventionnelle": {"classe_emploi": 4},
    },
]


@pytest.fixture
def mock_repo():
    with patch("app.modules.admin_import.application.seniority_import.repo") as mock:
        mock.find_company.return_value = {"id": "co-1", "company_name": "LEWIS"}
        mock.list_company_employees.return_value = EMPLOYEES
        yield mock


@pytest.fixture
def mock_list_extra():
    with patch(
        "app.modules.admin_import.application.seniority_import._list_employees_for_seniority",
        return_value=EMPLOYEES,
    ):
        yield


class TestSeniorityExcel:
    def test_detect_lewis_headers(self):
        headers = [
            "NOM",
            "PRENOM",
            "Statut",
            "Date ancienneté",
            "Nombre d'année d'ancienneté",
        ]
        mapping = detect_seniority_column_mapping(headers)
        assert mapping["last_name"] == "NOM"
        assert mapping["first_name"] == "PRENOM"
        assert mapping["seniority_date"] == "Date ancienneté"
        assert mapping["statut"] == "Statut"

    def test_parse_french_date(self):
        assert parse_seniority_date_cell("1/9/2010") == "2010-09-01"
        assert parse_seniority_date_cell("31/5/2026") == "2026-05-31"


class TestParseSeniorityImport:
    def test_matches_by_name(self, mock_repo, mock_list_extra):
        csv = (
            "NOM;PRENOM;Statut;Date ancienneté\n"
            "BOURMAULT;Francine;Non cadre;1/9/1988\n"
        ).encode("utf-8")
        result = parse_seniority_import_file(csv, "prime.csv", "co-1")
        assert result["summary"]["total"] == 1
        assert result["summary"]["ready"] == 1
        row = result["rows"][0]
        assert row["employee_id"] == "emp-1"
        assert row["seniority_date"] == "1988-09-01"

    def test_missing_date_column_raises(self, mock_repo, mock_list_extra):
        csv = "NOM;PRENOM\nBOURMAULT;Francine\n".encode("utf-8")
        with pytest.raises(ValueError, match="Date ancienneté"):
            parse_seniority_import_file(csv, "bad.csv", "co-1")

    def test_skips_instruction_rows(self, mock_repo, mock_list_extra):
        csv = (
            "NOM;PRENOM;Date ancienneté\n"
            "BOURMAULT;Francine;1/9/1988\n"
            "les cadres n'ont pas de prime d'ancienneté;;\n"
            "Pour les personnes en arrêt;;\n"
        ).encode("utf-8")
        result = parse_seniority_import_file(csv, "prime.csv", "co-1")
        assert result["summary"]["total"] == 1
        assert result["summary"]["skipped_junk"] == 2
        assert len(result["rows"]) == 1

    def test_reports_missing_active_employees(self, mock_repo, mock_list_extra):
        csv = (
            "NOM;PRENOM;Date ancienneté\n"
            "BOURMAULT;Francine;1/9/1988\n"
        ).encode("utf-8")
        result = parse_seniority_import_file(csv, "prime.csv", "co-1")
        assert result["summary"]["matched_employees"] == 1
        assert result["summary"]["missing_employees"] == 1
        missing = next(m for m in result["missing_employees"] if m["last_name"] == "CLEMENT")
        assert missing["employee_id"] == "emp-2"
        assert missing["current_hire_date"] == "2013-06-03"
        assert missing["current_seniority_date"] == "2013-06-03"

    def test_parses_row_with_commentaire_anciennete(self, mock_repo, mock_list_extra):
        employees = EMPLOYEES + [
            {
                "id": "emp-m",
                "first_name": "Francisco",
                "last_name": "MIRANDA",
                "email": "",
                "time_tracking_id": None,
                "employee_folder_name": "MIRANDA_Francisco",
                "employment_status": "actif",
                "hire_date": "2025-09-23",
                "seniority_reference_date": None,
                "statut": "Non cadre",
                "classification_conventionnelle": {"classe_emploi": 7},
            },
        ]
        with patch(
            "app.modules.admin_import.application.seniority_import._list_employees_for_seniority",
            return_value=employees,
        ):
            csv = (
                "NOM;PRENOM;Statut;Date ancienneté;Commentaire\n"
                "MIRANDA;Francisco;Non cadre;1/1/2009;"
                "Reprise ancienneté dernier contrat (autre société)\n"
            ).encode("utf-8")
            result = parse_seniority_import_file(csv, "prime.csv", "co-1")
        assert result["summary"]["total"] == 1
        assert result["summary"]["skipped_junk"] == 0
        row = result["rows"][0]
        assert row["employee_id"] == "emp-m"
        assert row["seniority_date"] == "2009-01-01"


class TestCommitSeniorityImport:
    def test_commit_updates_employee(self, mock_repo, mock_list_extra):
        with patch(
            "app.modules.admin_import.application.seniority_import.employee_commands.update_employee"
        ) as update:
            update.return_value = {
                "first_name": "Francine",
                "last_name": "BOURMAULT",
            }
            body = SeniorityImportCommitBody(
                company_id="co-1",
                rows=[
                    SeniorityImportCommitRow(
                        row_index=2,
                        employee_id="emp-1",
                        seniority_date="1988-09-01",
                        confirmed=True,
                    )
                ],
            )
            result = commit_seniority_import(body)
            assert result["applied"] == 1
            update.assert_called_once_with(
                "emp-1",
                {"seniority_reference_date": "1988-09-01"},
            )
