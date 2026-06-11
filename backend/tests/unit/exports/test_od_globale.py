"""Tests unitaires OD globale via registre unifié."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_ecritures_comptables as module
from app.modules.exports.infrastructure import payroll_ledger as ledger_module

pytestmark = pytest.mark.unit


class TestGenerateOdGlobale:
    def test_delegates_to_ledger_without_concatenation(self):
        sample_ecritures = [
            {
                "date_ecriture": "2026-06-30",
                "journal": "OD",
                "compte_comptable": "641000",
                "libelle": "Salaires Juin 2026",
                "debit": 3000.0,
                "credit": 0.0,
                "reference_export": "OD_PAIE_2026-06",
                "periode_paie": "2026-06",
            },
            {
                "date_ecriture": "2026-06-30",
                "journal": "OD",
                "compte_comptable": "425000",
                "libelle": "Net à payer Juin 2026",
                "debit": 0.0,
                "credit": 2200.0,
                "reference_export": "OD_PAIE_2026-06",
                "periode_paie": "2026-06",
            },
        ]
        od_totals = {
            "total_debit": 3000.0,
            "total_credit": 3000.0,
            "equilibre": True,
            "ecart": 0.0,
        }
        with patch.object(
            ledger_module,
            "build_payroll_ledger",
            return_value=(sample_ecritures, od_totals, {}),
        ) as build_mock:
            ecritures, totals, _ = module.generate_od_globale("co-1", "2026-06")

        build_mock.assert_called_once()
        assert build_mock.call_args.kwargs.get("scope") == "full"
        assert len(ecritures) == 2
        assert totals["equilibre"] is True

    def test_regroupement_parameter_forwarded(self):
        with patch.object(
            ledger_module,
            "build_payroll_ledger",
            return_value=([], {"total_debit": 0, "total_credit": 0, "equilibre": True, "ecart": 0}, {}),
        ) as build_mock:
            module.generate_od_globale(
                "co-1", "2026-06", regroupement="par_etablissement"
            )
        assert build_mock.call_args.kwargs.get("regroupement") == "par_etablissement"
