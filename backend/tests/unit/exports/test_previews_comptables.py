"""Ce que l'écran Exports montre d'une OD : bloquée, elle dit pourquoi et où."""

from unittest.mock import patch

import pytest

from app.modules.exports.application import queries
from app.modules.exports.infrastructure import export_ecritures_comptables as od_module
from app.modules.exports.infrastructure import export_formats_cabinet as cabinet
from app.modules.exports.infrastructure import payroll_ledger as ledger_module
from app.modules.exports.schemas import ExportPreviewRequest

pytestmark = pytest.mark.unit

ECRITURES_EQUILIBREES = [
    {"date_ecriture": "2026-09-30", "journal": "OD", "compte_comptable": "641000",
     "libelle": "Salaires Septembre 2026", "debit": 100.0, "credit": 0.0,
     "reference_export": "OD_PAIE_2026-09", "periode_paie": "2026-09", "nature": "brut"},
    {"date_ecriture": "2026-09-30", "journal": "OD", "compte_comptable": "421000",
     "libelle": "Net à payer Septembre 2026", "debit": 0.0, "credit": 100.0,
     "reference_export": "OD_PAIE_2026-09", "periode_paie": "2026-09", "nature": "net_a_payer"},
]

BULLETIN_INCOHERENT = {
    "code": "bulletin_incoherent",
    "label": "Bulletin dont le net ne se retrouve pas",
    "detail": "Salarié Témoin : le net à payer (100.0 €) diffère de 0.01 €",
    "montant": 0.01,
}

TOTAUX_BULLETINS = {
    "total_brut": 100.0,
    "total_net_a_payer": 100.0,
    "total_cotisations_salariales": 0.0,
    "total_cotisations_patronales": 0.0,
    "total_pas": 0.0,
    "employees_count": 1,
}


def _od_totals(equilibre=True, anomalies=()):
    return {
        "total_debit": 100.0,
        "total_credit": 100.0 if equilibre else 99.99,
        "equilibre": equilibre,
        "ecart": 0.0 if equilibre else 0.01,
        "anomalies": list(anomalies),
        "balance_debug": {},
    }


class TestPreviewOd:
    def test_bulletin_incoherent_nomme_dans_l_anomalie_bloquante(self):
        with patch.object(
            ledger_module,
            "build_payroll_ledger",
            return_value=(ECRITURES_EQUILIBREES, _od_totals(False, [BULLETIN_INCOHERENT]), {}),
        ), patch.object(
            od_module, "get_payslip_data_for_od", return_value=([], TOTAUX_BULLETINS)
        ):
            preview = od_module.preview_od("societe", "2026-09", "od_salaires")
        assert preview["can_generate"] is False
        messages = " ".join(a["message"] for a in preview["anomalies"])
        assert "Salarié Témoin" in messages


class TestPreviewFormatsCabinet:
    def test_previsualisation_complete_pour_l_ecran(self):
        """Elle renvoyait ni `employees_count` ni `totals` : l'écran tombait en
        erreur et la génération, gardée par la prévisualisation, aussi."""
        with patch.object(
            cabinet,
            "build_payroll_ledger",
            return_value=(ECRITURES_EQUILIBREES, _od_totals(), {}),
        ), patch.object(
            cabinet, "get_payslip_data_for_od", return_value=([], TOTAUX_BULLETINS)
        ):
            reponse = queries.preview_export(
                "societe",
                ExportPreviewRequest(export_type="export_cabinet_quadra", period="2026-09"),
            )
        assert reponse.can_generate is True
        assert reponse.employees_count == 1
        assert reponse.totals.total_amount == 100.0

    def test_od_bloquee_dit_pourquoi(self):
        with patch.object(
            cabinet,
            "build_payroll_ledger",
            return_value=(ECRITURES_EQUILIBREES, _od_totals(False, [BULLETIN_INCOHERENT]), {}),
        ), patch.object(
            cabinet, "get_payslip_data_for_od", return_value=([], TOTAUX_BULLETINS)
        ):
            preview = cabinet.preview_cabinet_export("societe", "2026-09", "export_cabinet_quadra")
        assert preview["can_generate"] is False
        assert any("Salarié Témoin" in a["message"] for a in preview["anomalies"])

    def test_fichier_quadra_refuse_si_l_od_ne_s_equilibre_pas(self):
        with patch.object(
            cabinet,
            "build_payroll_ledger",
            return_value=(ECRITURES_EQUILIBREES, _od_totals(False, [BULLETIN_INCOHERENT]), {}),
        ), pytest.raises(ledger_module.LedgerImbalanceError):
            cabinet.generate_cabinet_quadra_export("societe", "2026-09")
