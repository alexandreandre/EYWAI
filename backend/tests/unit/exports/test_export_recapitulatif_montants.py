"""Tests unitaires export récapitulatif des montants."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_recapitulatif_montants as module

pytestmark = pytest.mark.unit

MOCK_ROW = {
    "Matricule": "emp-1234",
    "Nom": "Dupont",
    "Prénom": "Jean",
    "Montant": 2500.0,
    "Devise": "EUR",
    "Statut_controle": "OK",
}


class TestPreviewRecapitulatifMontants:
    @patch.object(module, "get_paiement_salaires_data")
    def test_can_generate_with_payslips(self, mock_get):
        mock_get.return_value = (
            [MOCK_ROW],
            {"virements_count": 1, "total_amount": 2500.0},
            [],
            [],
        )
        preview = module.preview_recapitulatif_montants("company-1", "2025-06")

        assert preview["can_generate"] is True
        assert preview["totals"]["total_net_a_payer"] == 2500.0

    @patch.object(module, "get_paiement_salaires_data")
    def test_blocking_when_no_data(self, mock_get):
        mock_get.return_value = ([], {"virements_count": 0, "total_amount": 0.0}, [], [])
        preview = module.preview_recapitulatif_montants("company-1", "2025-06")

        assert preview["can_generate"] is False


class TestGenerateRecapitulatifMontants:
    @patch.object(module, "get_paiement_salaires_data")
    def test_csv_contains_headers(self, mock_get):
        mock_get.return_value = ([MOCK_ROW], {}, [], [])
        content = module.generate_recapitulatif_montants_export(
            "company-1", "2025-06", file_format="csv"
        )
        text = content.decode("utf-8")
        assert "Montant net à payer" in text
        assert "Dupont" in text
