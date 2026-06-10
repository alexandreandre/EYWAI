"""Tests unitaires OD globale (salaires + charges + PAS + acomptes)."""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_ecritures_comptables as module

pytestmark = pytest.mark.unit

SAMPLE_SAL_ECRI = [
    {
        "date_ecriture": "2026-06-30",
        "journal": "OD",
        "compte_comptable": "641000",
        "libelle": "Salaires Juin 2026",
        "debit": 3000.0,
        "credit": 0.0,
        "reference_export": "OD_SAL_2026-06",
        "periode_paie": "2026-06",
    },
    {
        "date_ecriture": "2026-06-30",
        "journal": "OD",
        "compte_comptable": "425000",
        "libelle": "Net à payer Juin 2026",
        "debit": 0.0,
        "credit": 2000.0,
        "reference_export": "OD_SAL_2026-06",
        "periode_paie": "2026-06",
    },
]

SAMPLE_CHG_ECRI = [
    {
        "date_ecriture": "2026-06-30",
        "journal": "OD",
        "compte_comptable": "645000",
        "libelle": "Charges URSSAF",
        "debit": 500.0,
        "credit": 0.0,
        "reference_export": "OD_CHG_2026-06",
        "periode_paie": "2026-06",
    },
]

SAMPLE_PAS_ECRI = [
    {
        "date_ecriture": "2026-06-30",
        "journal": "OD",
        "compte_comptable": "425100",
        "libelle": "PAS Juin 2026",
        "debit": 100.0,
        "credit": 0.0,
        "reference_export": "OD_PAS_2026-06",
        "periode_paie": "2026-06",
    },
]


class TestGenerateOdGlobale:
    def test_combines_salaires_charges_pas(self):
        with patch.object(module, "generate_od_salaires") as sal:
            with patch.object(module, "generate_od_charges_sociales") as chg:
                with patch.object(module, "generate_od_pas") as pas:
                    with patch(
                        "app.modules.exports.infrastructure.export_acomptes.get_repayments_total_by_account",
                        return_value={},
                    ):
                        sal.return_value = (SAMPLE_SAL_ECRI, {}, {"net_a_payer": {"compte_comptable": "425000"}})
                        chg.return_value = (SAMPLE_CHG_ECRI, {}, {})
                        pas.return_value = (SAMPLE_PAS_ECRI, {}, {})
                        ecritures, od_totals, _ = module.generate_od_globale(
                            "co-1", "2026-06"
                        )

        assert len(ecritures) == 4
        libelles = [e["libelle"] for e in ecritures]
        assert any("Salaires" in l for l in libelles)
        assert any("Charges URSSAF" in l for l in libelles)
        assert any("PAS" in l for l in libelles)
        assert od_totals["equilibre"] is False  # mock partial data

    def test_adds_repayment_credits_and_rebalances_net(self):
        with patch.object(module, "generate_od_salaires") as sal:
            with patch.object(module, "generate_od_charges_sociales") as chg:
                with patch.object(module, "generate_od_pas") as pas:
                    with patch(
                        "app.modules.exports.infrastructure.export_acomptes.get_repayments_total_by_account",
                        return_value={"4251": 500.0},
                    ):
                        sal_ecritures = [dict(e) for e in SAMPLE_SAL_ECRI]
                        sal.return_value = (
                            sal_ecritures,
                            {},
                            {"net_a_payer": {"compte_comptable": "425000", "journal": "OD"}},
                        )
                        chg.return_value = ([], {}, {})
                        pas.return_value = ([], {}, {})
                        ecritures, od_totals, _ = module.generate_od_globale(
                            "co-1", "2026-06"
                        )

        net_line = next(e for e in ecritures if "Net à payer" in e["libelle"])
        assert net_line["credit"] == 2500.0

        acompte_line = next(
            e for e in ecritures if e["compte_comptable"] == "4251"
        )
        assert acompte_line["credit"] == 500.0
        assert od_totals["equilibre"] is True
