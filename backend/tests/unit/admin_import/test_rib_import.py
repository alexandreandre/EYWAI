"""Tests unitaires — rapprochement employé import RIB."""

from unittest.mock import patch

import pytest

from app.modules.admin_import.application.rib_import import parse_rib_import_file


EMPLOYEES = [
    {
        "id": "emp-1",
        "first_name": "Paul",
        "last_name": "Martin",
        "email": "paul@example.com",
        "time_tracking_id": "196",
        "employee_folder_name": "Martin_Paul",
        "coordonnees_bancaires": {},
        "employment_status": "actif",
    },
    {
        "id": "emp-2",
        "first_name": "Sophie",
        "last_name": "Durand",
        "email": "sophie@example.com",
        "time_tracking_id": "270",
        "employee_folder_name": "Durand_Sophie",
        "coordonnees_bancaires": {"iban": "FR1420041010050500013M02606"},
        "employment_status": "actif",
    },
]


@pytest.fixture
def mock_repo():
    with patch("app.modules.admin_import.application.rib_import.repo") as mock:
        mock.find_company.return_value = {"id": "co-1", "company_name": "Test SA"}
        mock.list_company_employees.return_value = EMPLOYEES
        yield mock


class TestParseRibImportFile:
    def test_matches_by_name_high_confidence(self, mock_repo):
        csv = (
            "Nom,Prénom,RIB\n"
            "Martin,Paul,FR1420041010050500013M02606\n"
        ).encode("utf-8")
        result = parse_rib_import_file(csv, "ribs.csv", "co-1")
        assert result["summary"]["total"] == 1
        assert result["summary"]["ready"] == 1
        row = result["rows"][0]
        assert row["employee_id"] == "emp-1"
        assert row["review_status"] == "ok"
        assert row["iban_valid"] is True

    def test_warns_on_fuzzy_match(self, mock_repo):
        csv = (
            "Nom,Prénom,RIB\n"
            "MARTIN,Paule,FR1420041010050500013M02606\n"
        ).encode("utf-8")
        result = parse_rib_import_file(csv, "ribs.csv", "co-1")
        row = result["rows"][0]
        assert row["employee_id"] == "emp-1"
        assert row["review_status"] in ("ok", "warning")

    def test_error_without_identity(self, mock_repo):
        csv = "RIB\nFR1420041010050500013M02606\n".encode("utf-8")
        result = parse_rib_import_file(csv, "ribs.csv", "co-1")
        row = result["rows"][0]
        assert row["employee_id"] is None
        assert row["review_status"] == "error"

    def test_missing_rib_column_raises(self, mock_repo):
        csv = "Nom,Prénom\nMartin,Paul\n".encode("utf-8")
        with pytest.raises(ValueError, match="RIB"):
            parse_rib_import_file(csv, "ribs.csv", "co-1")

    def test_includes_roster(self, mock_repo):
        csv = "Nom,Prénom,RIB\nMartin,Paul,FR1420041010050500013M02606\n".encode("utf-8")
        result = parse_rib_import_file(csv, "ribs.csv", "co-1")
        assert len(result["roster"]) == 2

    def test_raises_when_no_employees(self, mock_repo):
        mock_repo.list_company_employees.return_value = []
        csv = "Nom,Prénom,RIB\nMartin,Paul,FR1420041010050500013M02606\n".encode("utf-8")
        with pytest.raises(ValueError, match="Aucun salarié"):
            parse_rib_import_file(csv, "ribs.csv", "co-1")
