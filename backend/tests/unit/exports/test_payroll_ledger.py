"""Tests du registre paie unifié — non-duplication OD globale."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_ecritures_comptables as od_module
from app.modules.exports.infrastructure import payroll_ledger as ledger_module

pytestmark = pytest.mark.unit

SAMPLE_PAYSLIPS = [
    {
        "employee_id": "emp-1",
        "brut": 3000.0,
        "net_a_payer": 2200.0,
        "cotisations_salariales": 400.0,
        "cotisations_patronales": 600.0,
        "pas": 100.0,
        "cotisations_detail": [
            {
                "libelle": "URSSAF",
                "montant_salarial": 400.0,
                "montant_patronal": 600.0,
            }
        ],
    }
]


class TestPayrollLedgerNoDuplication:
    def test_od_globale_uses_single_ledger_pass(self):
        with patch.object(
            ledger_module, "build_payroll_ledger"
        ) as build_mock:
            build_mock.return_value = (
                [],
                {"total_debit": 0, "total_credit": 0, "equilibre": True, "ecart": 0},
                {},
            )
            with patch.object(
                ledger_module,
                "ledger_to_od_export_rows",
                return_value=[],
            ):
                _, od_totals, _ = od_module.generate_od_globale("co-1", "2026-06")

        build_mock.assert_called_once()
        assert build_mock.call_args.kwargs.get("scope") == "full"
        assert od_totals["equilibre"] is True

    def test_scopes_use_different_ledger_filters(self):
        with patch.object(ledger_module, "build_payroll_ledger") as build_mock:
            with patch.object(
                ledger_module, "ledger_to_od_export_rows", side_effect=lambda rows: rows
            ):
                build_mock.side_effect = [
                    ([], {"total_debit": 100, "equilibre": True}, {}),
                    ([], {"total_debit": 50, "equilibre": True}, {}),
                ]
                od_module.generate_od_globale("co-1", "2026-06")
                od_module.generate_od_salaires("co-1", "2026-06")

        assert build_mock.call_count == 2
        assert build_mock.call_args_list[0].kwargs.get("scope") == "full"
        assert build_mock.call_args_list[1].kwargs.get("scope") == "salaires"


class TestPayrollLedgerPatronalBalance:
    def _default_mappings(self):
        return {
            "salaire_brut": {"compte_comptable": "641000", "journal": "OD"},
            "net_a_payer": {"compte_comptable": "425000", "journal": "OD"},
            "cotisation_salariale": {"compte_comptable": "425000", "journal": "OD"},
            "cotisation_patronale": {"compte_comptable": "645000", "journal": "OD"},
            "dette_organisme": {"compte_comptable": "431000", "journal": "OD"},
            "pas": {"compte_comptable": "442000", "journal": "OD"},
        }

    def test_allegements_patronaux_equilibrent_645_et_431(self):
        payslip_list = [
            {
                "employee_name": "Alice",
                "brut": 3000.0,
                "net_a_payer": 2400.0,
                "cotisations_salariales": 600.0,
                "cotisations_patronales": 500.0,
                "pas": 0.0,
                "cotisations_detail": [
                    {
                        "libelle": "URSSAF",
                        "montant_salarial": 600.0,
                        "montant_patronal": 600.0,
                    },
                    {
                        "libelle": "Réduction générale",
                        "montant_salarial": 0.0,
                        "montant_patronal": -100.0,
                    },
                ],
            }
        ]
        totals = {
            "total_brut": 3000.0,
            "total_net_a_payer": 2400.0,
            "total_cotisations_salariales": 600.0,
            "total_cotisations_patronales": 500.0,
            "total_pas": 0.0,
            "employees_count": 1,
        }

        with patch.object(
            ledger_module,
            "get_payslip_data_for_od",
            return_value=(payslip_list, totals),
        ), patch.object(
            ledger_module,
            "get_accounting_mappings",
            return_value=self._default_mappings(),
        ), patch(
            "app.modules.exports.infrastructure.export_acomptes.get_acomptes_data",
            return_value=([], [], [], {}),
        ), patch(
            "app.modules.exports.infrastructure.export_saisies.get_saisies_data",
            return_value=([], [], {}),
        ), patch.object(
            ledger_module,
            "list_loan_repayments_by_period",
            return_value=[],
        ), patch(
            "app.modules.exports.infrastructure.export_notes_frais.get_notes_frais_ecritures",
            return_value=[],
        ):
            ecritures, od_totals, _ = ledger_module.build_payroll_ledger(
                "co-1",
                "2026-06",
                include_notes_frais=False,
                scope="full",
            )

        assert od_totals["equilibre"] is True
        assert od_totals["ecart"] == 0.0
        charges_645 = sum(e["debit"] for e in ecritures if e["compte_comptable"] == "645000")
        allegements_645 = sum(e["credit"] for e in ecritures if e["compte_comptable"] == "645000")
        dettes_431 = sum(e["credit"] for e in ecritures if e["compte_comptable"] == "431000")
        assert charges_645 == pytest.approx(600.0)
        assert allegements_645 == pytest.approx(100.0)
        assert dettes_431 == pytest.approx(500.0)
        assert od_totals["balance_debug"]["reconciliation"]["ecart_645_net_vs_431"] == 0.0
