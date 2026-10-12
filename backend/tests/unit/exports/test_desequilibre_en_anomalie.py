"""Un déséquilibre de l'OD globale ou du FEC est listé à l'aperçu, pas levé en erreur.

Avant, l'aperçu de l'OD globale et celui du FEC levaient `LedgerImbalanceError`
(traduite en 422) : l'écran n'avait qu'un message d'erreur. Les OD partielles,
elles, listaient les lignes en anomalies bloquantes. Maintenant les deux
aperçus font de même ; la génération, elle, garde son refus.
"""

from unittest.mock import patch

import pytest

from app.modules.exports.infrastructure import export_ecritures_comptables, export_fec
from app.modules.exports.infrastructure.payroll_ledger import LedgerImbalanceError

pytestmark = pytest.mark.unit

DESEQUILIBRE = {
    "equilibre": False,
    "ecart": 437.53,
    "total_debit": 1000.0,
    "total_credit": 562.47,
    "anomalies": [
        {
            "code": "element_hors_brut_non_mappe",
            "label": "Élément hors brut sans compte comptable",
            "detail": "panier — Paniers jours non soumis",
            "montant": 437.53,
        }
    ],
}
ECRITURE = {
    "date_ecriture": "2026-09-30",
    "journal": "OD",
    "compte_comptable": "641100",
    "libelle": "Salaires",
    "debit": 1000.0,
    "credit": 0.0,
    "periode_paie": "2026-09",
}


def _grand_livre(od_totals):
    return patch(
        "app.modules.exports.infrastructure.payroll_ledger.build_payroll_ledger",
        return_value=([ECRITURE], od_totals, {}),
    )


class TestApercuOdGlobale:
    def _apercu(self):
        with _grand_livre(DESEQUILIBRE), patch.object(
            export_ecritures_comptables,
            "get_payslip_data_for_od",
            return_value=([], {"employees_count": 4}),
        ):
            return export_ecritures_comptables.preview_od("co-1", "2026-09", "od_globale")

    def test_ne_leve_pas_d_erreur(self):
        self._apercu()

    def test_liste_l_ecart_et_ce_qui_manque_en_anomalies_bloquantes(self):
        apercu = self._apercu()
        messages = [a["message"] for a in apercu["anomalies"]]
        assert any("OD non équilibrée" in m and "437.53" in m for m in messages)
        assert any("Paniers jours non soumis" in m for m in messages)
        assert all(a["severity"] == "blocking" for a in apercu["anomalies"])
        assert apercu["can_generate"] is False

    def test_la_generation_garde_son_refus(self):
        with _grand_livre(DESEQUILIBRE), pytest.raises(LedgerImbalanceError):
            export_ecritures_comptables.generate_od_globale("co-1", "2026-09")


class TestApercuFec:
    def _apercu(self):
        with patch.object(
            export_fec,
            "build_payroll_ledger",
            return_value=([ECRITURE], DESEQUILIBRE, {}),
        ):
            return export_fec.preview_fec("co-1", "2026-09")

    def test_ne_leve_pas_d_erreur(self):
        self._apercu()

    def test_liste_l_ecart_et_ce_qui_manque(self):
        apercu = self._apercu()
        messages = [a["message"] for a in apercu["anomalies"]]
        assert any("Écritures non équilibrées" in m and "437.53" in m for m in messages)
        assert any("Paniers jours non soumis" in m for m in messages)
        assert apercu["can_generate"] is False

    def test_la_generation_garde_son_refus(self):
        with patch.object(
            export_fec, "build_payroll_ledger", return_value=([ECRITURE], DESEQUILIBRE, {})
        ), pytest.raises(LedgerImbalanceError):
            export_fec.generate_fec_export("co-1", "2026-09")
