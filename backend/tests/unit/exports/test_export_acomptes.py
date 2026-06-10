"""Tests unitaires export acomptes & avances."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_acomptes as module

pytestmark = pytest.mark.unit

SAMPLE_PAYMENTS = [
    {
        "employee_id": "emp-1",
        "employee_name": "Jean Dupont",
        "advance_type": "acompte_salaire",
        "advance_type_label": "Acompte sur salaire",
        "accounting_account": "4251",
        "amount_paid": 500.0,
        "amount_repaid": 0.0,
        "event_type": "versement",
        "event_date": "2026-06-15",
        "advance_status": "paid",
        "prime_label": None,
    }
]

SAMPLE_REPAYMENTS = [
    {
        "employee_id": "emp-1",
        "employee_name": "Jean Dupont",
        "advance_type": "acompte_salaire",
        "advance_type_label": "Acompte sur salaire",
        "accounting_account": "4251",
        "amount_paid": 0.0,
        "amount_repaid": 500.0,
        "event_type": "remboursement",
        "event_date": "2026-06-01",
        "advance_status": "paid",
        "prime_label": None,
    }
]


class TestBuildListRows:
    def test_builds_versement_and_remboursement_rows(self):
        rows = module._build_list_rows(SAMPLE_PAYMENTS, SAMPLE_REPAYMENTS)
        assert len(rows) == 2
        assert rows[0]["Évènement"] == "Versement"
        assert rows[0]["Montant versé"] == 500.0
        assert rows[1]["Évènement"] == "Remboursement"
        assert rows[1]["Montant remboursé"] == 500.0
        assert rows[0]["Compte comptable"] == "4251"


class TestGenerateAcomptesEcritures:
    def test_versement_debit_425_credit_banque(self):
        with patch.object(module, "get_bank_account", return_value="512000"):
            ecritures = module.generate_acomptes_ecritures(
                "co-1",
                "2026-06",
                SAMPLE_PAYMENTS,
                [],
            )
        assert len(ecritures) == 2
        assert ecritures[0]["compte_comptable"] == "4251"
        assert ecritures[0]["debit"] == 500.0
        assert ecritures[1]["compte_comptable"] == "512000"
        assert ecritures[1]["credit"] == 500.0

    def test_remboursement_debit_net_credit_425(self):
        ecritures = module.generate_acomptes_ecritures(
            "co-1",
            "2026-06",
            [],
            SAMPLE_REPAYMENTS,
        )
        assert len(ecritures) == 2
        assert ecritures[0]["compte_comptable"] == "425000"
        assert ecritures[0]["debit"] == 500.0
        assert ecritures[1]["compte_comptable"] == "4251"
        assert ecritures[1]["credit"] == 500.0


class TestPreviewAcomptes:
    def test_preview_with_data(self):
        with patch.object(
            module,
            "get_acomptes_data",
            return_value=(SAMPLE_PAYMENTS, SAMPLE_REPAYMENTS, [], {
                "employees_count": 1,
                "total_amount": 1000.0,
                "total_versements": 500.0,
                "total_remboursements": 500.0,
                "operations_count": 2,
                "totals_by_account": {},
            }),
        ):
            with patch.object(module, "generate_acomptes_ecritures", return_value=[]):
                preview = module.preview_acomptes("co-1", "2026-06")

        assert preview["can_generate"] is True
        assert preview["employees_count"] == 1
        assert preview["totals"]["total_versements"] == 500.0

    def test_preview_empty_period_warns(self):
        with patch.object(
            module,
            "get_acomptes_data",
            return_value=([], [], [], {
                "employees_count": 0,
                "total_amount": 0.0,
                "total_versements": 0.0,
                "total_remboursements": 0.0,
                "operations_count": 0,
                "totals_by_account": {},
            }),
        ):
            with patch.object(module, "generate_acomptes_ecritures", return_value=[]):
                preview = module.preview_acomptes("co-1", "2026-06")

        assert preview["can_generate"] is True
        assert any("Aucun versement" in w for w in preview["warnings"])
