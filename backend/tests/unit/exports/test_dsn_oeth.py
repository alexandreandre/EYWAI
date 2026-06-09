"""Tests export DSN OETH."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.exports.infrastructure.export_dsn import generate_dsn_xml


@patch("app.modules.exports.infrastructure.export_dsn.get_dsn_employees_data")
@patch("app.modules.exports.infrastructure.export_dsn.get_company_data")
@patch("app.modules.exports.infrastructure.export_dsn.oeth_queries")
def test_generate_dsn_xml_includes_boeth(mock_oeth, mock_company, mock_employees):
    mock_company.return_value = {
        "siret": "12345678901234",
        "code_naf": "6201Z",
        "address": {"rue": "1 rue Test", "code_postal": "75001", "ville": "Paris"},
    }
    mock_employees.return_value = (
        [
            {
                "employee": {
                    "id": "emp-1",
                    "first_name": "Jean",
                    "last_name": "Dupont",
                    "nir": "123456789012345",
                    "contract_type": "CDI",
                    "hire_date": "2020-01-01",
                },
                "payslip": {"payslip_data": {"salaire_brut": 2500}},
                "brut": 2500,
                "net_imposable": 2000,
                "pas": 100,
                "cotisations_detail": [],
            }
        ],
        {},
    )
    mock_oeth.get_boeth_code_for_employee.return_value = "01"
    mock_oeth.get_previous_boeth_for_period.return_value = None
    mock_oeth.build_dsn_payload.return_value = MagicMock(
        complement_oeth=[],
        cotisations_etablissement=[],
        cotisation_agregee=None,
    )

    xml = generate_dsn_xml("company-1", "2025-06", "dsn_mensuelle")
    content = xml.decode("utf-8")
    assert "StatutBOETH" in content
    assert ">01<" in content
