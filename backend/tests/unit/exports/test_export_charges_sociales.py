"""Tests unitaires export charges sociales par caisse."""

from unittest.mock import patch

import pytest

from app.modules.exports.domain.charges_organisme import (
    ORGANISME_RETRAITE,
    ORGANISME_URSSAF,
    resolve_organisme,
)
from app.modules.exports.infrastructure import export_charges_sociales as module

pytestmark = pytest.mark.unit


class TestResolveOrganisme:
    def test_urssaf(self):
        assert resolve_organisme("Cotisation URSSAF maladie") == ORGANISME_URSSAF

    def test_retraite(self):
        assert resolve_organisme("Retraite AGIRC-ARRCO") == ORGANISME_RETRAITE

    def test_autre(self):
        assert resolve_organisme("Taxe d'apprentissage") == "AUTRE"


SAMPLE_PAYSLIPS = [
    {
        "employee_id": "emp-1",
        "cotisations_detail": [
            {
                "libelle": "URSSAF Maladie",
                "montant_salarial": 100.0,
                "montant_patronal": 200.0,
            },
            {
                "libelle": "Retraite AGIRC-ARRCO",
                "montant_salarial": 50.0,
                "montant_patronal": 75.0,
            },
        ],
    },
    {
        "employee_id": "emp-2",
        "cotisations_detail": [
            {
                "libelle": "URSSAF Maladie",
                "montant_salarial": 80.0,
                "montant_patronal": 160.0,
            },
        ],
    },
]


class TestAggregateCharges:
    def test_aggregates_by_organisme_and_detail(self):
        detail, summary, totals = module._aggregate_charges(SAMPLE_PAYSLIPS)

        assert len(detail) == 2
        urssaf_detail = next(r for r in detail if r["Organisme"] == ORGANISME_URSSAF)
        assert urssaf_detail["Part salariale"] == 180.0
        assert urssaf_detail["Part patronale"] == 360.0
        assert urssaf_detail["Total cotisations"] == 540.0

        assert len(summary) == 2
        urssaf_summary = next(r for r in summary if r["Organisme"] == ORGANISME_URSSAF)
        assert urssaf_summary["Nombre de salariés"] == 2

        assert totals["employees_count"] == 2
        assert totals["total_cotisations_salariales"] == 230.0
        assert totals["total_cotisations_patronales"] == 435.0
        assert totals["total_amount"] == 665.0

    def test_filters_by_caisses(self):
        detail, summary, totals = module._aggregate_charges(
            SAMPLE_PAYSLIPS, caisses=[ORGANISME_URSSAF]
        )

        assert all(r["Organisme"] == ORGANISME_URSSAF for r in detail)
        assert len(summary) == 1
        assert totals["total_cotisations_salariales"] == 180.0


class TestGenerateExport:
    @patch.object(module, "get_charges_sociales_data")
    def test_xlsx_starts_with_pk_zip_header(self, mock_get_data):
        mock_get_data.return_value = (
            [
                {
                    "Organisme": ORGANISME_URSSAF,
                    "Libellé cotisation": "URSSAF Maladie",
                    "Part salariale": 180.0,
                    "Part patronale": 360.0,
                    "Total cotisations": 540.0,
                }
            ],
            [
                {
                    "Organisme": ORGANISME_URSSAF,
                    "Nombre de salariés": 2,
                    "Part salariale": 180.0,
                    "Part patronale": 360.0,
                    "Total cotisations": 540.0,
                }
            ],
            {"employees_count": 2},
        )

        content = module.generate_charges_sociales_export(
            "company-1", "2025-06", format="xlsx"
        )
        assert content[:2] == b"PK"

    @patch.object(module, "get_charges_sociales_data")
    def test_csv_contains_headers(self, mock_get_data):
        mock_get_data.return_value = (
            [
                {
                    "Organisme": ORGANISME_URSSAF,
                    "Libellé cotisation": "URSSAF Maladie",
                    "Part salariale": 180.0,
                    "Part patronale": 360.0,
                    "Total cotisations": 540.0,
                }
            ],
            [],
            {"employees_count": 2},
        )

        content = module.generate_charges_sociales_export(
            "company-1", "2025-06", format="csv"
        )
        text = content.decode("utf-8-sig")
        assert "Organisme" in text
        assert "URSSAF Maladie" in text


class TestPreviewChargesSociales:
    @patch.object(module, "get_charges_sociales_data")
    def test_preview_includes_organismes_details(self, mock_get_data):
        mock_get_data.return_value = (
            [],
            [
                {
                    "Organisme": ORGANISME_URSSAF,
                    "Nombre de salariés": 2,
                    "Part salariale": 180.0,
                    "Part patronale": 360.0,
                    "Total cotisations": 540.0,
                }
            ],
            {
                "employees_count": 2,
                "total_cotisations_salariales": 180.0,
                "total_cotisations_patronales": 360.0,
                "total_amount": 540.0,
            },
        )

        preview = module.preview_charges_sociales("company-1", "2025-06")
        assert preview["employees_count"] == 2
        assert len(preview["details"]["organismes"]) == 1
        assert preview["details"]["organismes"][0]["organisme"] == ORGANISME_URSSAF
        assert preview["can_generate"] is True
