"""Tests unitaires export saisies sur salaire."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_saisies as module

pytestmark = pytest.mark.unit

SAMPLE_DEDUCTIONS = [
    {
        "employee_id": "emp-1",
        "employee_name": "Jean Dupont",
        "seizure_type": "pension_alimentaire",
        "seizure_type_label": "Pension alimentaire",
        "creditor_name": "CAF Paris",
        "accounting_account": "4272",
        "deducted_amount": 350.0,
        "seizable_amount": 400.0,
        "net_salary": 2200.0,
        "seizure_status": "active",
        "period": "2026-06",
        "seizure_id": "seizure-abc12345",
    }
]


class TestBuildListRows:
    def test_builds_deduction_row(self):
        rows = module._build_list_rows(SAMPLE_DEDUCTIONS)
        assert len(rows) == 1
        assert rows[0]["Employé"] == "Jean Dupont"
        assert rows[0]["Type de saisie"] == "Pension alimentaire"
        assert rows[0]["Créancier"] == "CAF Paris"
        assert rows[0]["Montant prélevé"] == 350.0
        assert rows[0]["Compte comptable"] == "4272"


class TestGenerateSaisiesEcritures:
    def test_prelevement_debit_net_credit_opposition(self):
        ecritures = module.generate_saisies_ecritures(
            "co-1",
            "2026-06",
            SAMPLE_DEDUCTIONS,
        )
        assert len(ecritures) == 2
        assert ecritures[0]["compte_comptable"] == "425000"
        assert ecritures[0]["debit"] == 350.0
        assert ecritures[1]["compte_comptable"] == "4272"
        assert ecritures[1]["credit"] == 350.0
        assert "Pension alimentaire" in ecritures[0]["libelle"]
        assert "CAF Paris" in ecritures[0]["libelle"]


class TestPreviewSaisies:
    def test_preview_with_data(self):
        with patch.object(
            module,
            "get_saisies_data",
            return_value=(SAMPLE_DEDUCTIONS, [], {
                "employees_count": 1,
                "total_amount": 350.0,
                "total_prelevements": 350.0,
                "operations_count": 1,
                "totals_by_account": {},
            }),
        ):
            with patch.object(module, "generate_saisies_ecritures", return_value=[]):
                preview = module.preview_saisies("co-1", "2026-06")

        assert preview["can_generate"] is True
        assert preview["employees_count"] == 1
        assert preview["totals"]["total_prelevements"] == 350.0

    def test_preview_empty_period_warns(self):
        with patch.object(
            module,
            "get_saisies_data",
            return_value=([], [], {
                "employees_count": 0,
                "total_amount": 0.0,
                "total_prelevements": 0.0,
                "operations_count": 0,
                "totals_by_account": {},
            }),
        ):
            with patch.object(module, "generate_saisies_ecritures", return_value=[]):
                preview = module.preview_saisies("co-1", "2026-06")

        assert preview["can_generate"] is True
        assert any("Aucun prélèvement" in w for w in preview["warnings"])

    def test_preview_warns_missing_creditor(self):
        deductions = [{**SAMPLE_DEDUCTIONS[0], "creditor_name": ""}]
        with patch.object(
            module,
            "get_saisies_data",
            return_value=(deductions, [], {
                "employees_count": 1,
                "total_amount": 350.0,
                "total_prelevements": 350.0,
                "operations_count": 1,
                "totals_by_account": {},
            }),
        ):
            with patch.object(module, "generate_saisies_ecritures", return_value=[]):
                preview = module.preview_saisies("co-1", "2026-06")

        assert any("Créancier manquant" in a["message"] for a in preview["anomalies"])
