"""Tests company setup status."""

from unittest.mock import MagicMock, patch

import pytest

from app.modules.admin_import.application.company_setup_status import get_company_setup_status


@pytest.fixture
def mock_company():
    return {
        "id": "co-1",
        "company_name": "Test SA",
        "siret": "12345678901234",
        "idcc": "1979",
        "taux_at_mp": 3.5,
        "taux_vm": None,
        "taux_fnal": None,
        "paie_jour_de_fin": 31,
        "paie_occurrence": -1,
        "dsn_sync_mode": "transition",
    }


@patch("app.modules.admin_import.application.company_setup_status._payroll_kpi_block")
@patch("app.modules.admin_import.application.company_setup_status._db")
@patch("app.modules.admin_import.application.company_setup_status.compute_coverage")
@patch("app.modules.admin_import.application.company_setup_status._company_row")
def test_get_company_setup_status_ok(
    mock_row, mock_coverage, mock_db, mock_payroll_kpi, mock_company
):
    mock_row.return_value = mock_company
    mock_payroll_kpi.return_value = {
        "ready": False,
        "source": "none",
        "source_label": "Aucune donnée paie",
        "period": "2026-05",
        "gross": 0.0,
        "net": 0.0,
        "partial": False,
    }
    mock_coverage.return_value = {
        "months_covered": ["2026-01", "2026-02"],
        "last_period": "2026-02",
        "status": "ok",
        "expected_last_period": "2026-02",
        "gaps": [],
        "timeline": [
            {"period": "2026-01", "month": 1, "state": "covered"},
            {"period": "2026-02", "month": 2, "state": "covered"},
            {"period": "2026-03", "month": 3, "state": "future"},
        ],
    }

    client = MagicMock()
    mock_db.return_value = client

    def table(name):
        t = MagicMock()
        if name == "employees":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[
                    {
                        "id": "e1",
                        "employment_status": "actif",
                        "nir": "123",
                        "date_naissance": "1990-01-01",
                        "adresse": {"rue": "x"},
                        "salaire_de_base": {"valeur": 2000},
                        "coordonnees_bancaires": {"iban": "FR7630001007941234567890185"},
                    }
                ]
            )
        elif name == "employee_leave_adjustments":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(count=1)
        elif name == "company_leave_settings":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"id": "ls1"}]
            )
        elif name == "company_modulation_settings":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[{"enabled": True}]
            )
        elif name == "company_jei_settings":
            t.select.return_value.eq.return_value.limit.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        elif name == "company_oeth_annual_reviews":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        elif name == "employee_schedules":
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[{"month": 1}, {"month": 2}]
            )
        return t

    client.table.side_effect = table

    result = get_company_setup_status("co-1")
    assert result["company_id"] == "co-1"
    assert result["overall_pct"] > 0
    assert result["blocks"]["dsn"]["covered_months"] == 2
    assert result["blocks"]["dsn"]["applicable_covered_months"] == 2
    assert result["blocks"]["dsn"]["complete"] is True
    assert result["blocks"]["dsn"]["employees_synced"] is True
    assert isinstance(result["next_actions"], list)


@patch("app.modules.admin_import.application.company_setup_status._payroll_kpi_block")
@patch("app.modules.admin_import.application.company_setup_status._db")
@patch("app.modules.admin_import.application.company_setup_status.compute_coverage")
@patch("app.modules.admin_import.application.company_setup_status._company_row")
def test_get_company_setup_status_empty_employees(
    mock_row, mock_coverage, mock_db, mock_payroll_kpi, mock_company
):
    mock_row.return_value = mock_company
    mock_payroll_kpi.return_value = {
        "ready": False,
        "source": "none",
        "source_label": "Aucune donnée paie",
        "period": "2026-05",
        "gross": 0.0,
        "net": 0.0,
        "partial": False,
    }
    mock_coverage.return_value = {
        "months_covered": ["2026-01", "2026-02", "2026-03"],
        "last_period": "2026-03",
        "status": "never",
        "expected_last_period": "2026-05",
        "gaps": ["2026-04", "2026-05"],
        "timeline": [
            {"period": f"2026-{m:02d}", "month": m, "state": "covered" if m <= 3 else "missing"}
            for m in range(1, 6)
        ],
    }

    client = MagicMock()
    mock_db.return_value = client

    def table(name):
        t = MagicMock()
        if name == "employees":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        elif name == "employee_leave_adjustments":
            t.select.return_value.eq.return_value.execute.return_value = MagicMock(count=0)
        elif name == "company_leave_settings":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )
        elif name == "company_modulation_settings":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(
                data=[]
            )
        elif name == "company_jei_settings":
            t.select.return_value.eq.return_value.limit.return_value.maybe_single.return_value.execute.return_value = MagicMock(
                data=None
            )
        elif name == "company_oeth_annual_reviews":
            t.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
        elif name == "employee_schedules":
            t.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        return t

    client.table.side_effect = table

    result = get_company_setup_status("co-1")
    assert result["blocks"]["employees"]["total"] == 0
    assert result["blocks"]["employees"]["empty"] is True
    assert result["blocks"]["dsn"]["status"] == "stale"
    assert result["blocks"]["dsn"]["complete"] is False
    assert result["blocks"]["dsn"]["employees_synced"] is False
    assert result["next_actions"][0]["block"] == "employees_empty"
    assert "DSN" in result["next_actions"][0]["label"]
