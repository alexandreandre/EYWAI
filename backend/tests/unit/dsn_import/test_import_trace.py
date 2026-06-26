"""Tests traces import DSN."""

from unittest.mock import patch

from app.modules.dsn_import.application.import_trace import diagnose_employee_match


@patch("app.modules.dsn_import.application.import_trace.repo.find_employee_by_nir")
@patch("app.modules.dsn_import.application.import_trace.repo.find_employee_by_nir_global")
def test_diagnose_employee_match_by_nir_company(mock_global, mock_company):
    mock_company.return_value = {
        "id": "emp-1",
        "company_id": "co-1",
        "email": "a@b.fr",
        "user_id": "u-1",
        "employment_status": "actif",
    }
    mock_global.return_value = None

    out = diagnose_employee_match(
        "co-1",
        "1234567890123",
        "emp:siret:ident",
        {"first_name": "A", "last_name": "B"},
    )

    assert out["match"] == "by_nir_company"
    assert out["existing_id"] == "emp-1"
    mock_global.assert_not_called()


@patch("app.modules.dsn_import.application.import_trace.repo.find_employee_by_nir")
@patch("app.modules.dsn_import.application.import_trace.repo.find_employee_by_nir_global")
def test_diagnose_employee_match_none(mock_global, mock_company):
    mock_company.return_value = None
    mock_global.return_value = None

    out = diagnose_employee_match(
        "co-1",
        "1234567890123",
        "emp:siret:ident",
        {"first_name": "A", "last_name": "B"},
    )

    assert out["match"] == "none"
    assert out["note"] == "nir_not_in_db"
