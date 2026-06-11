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
