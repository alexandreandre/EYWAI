"""Contrôle d'un export comptable : équilibre, complétude, natures au centime."""

import pytest

from app.modules.exports.domain.accounting_plan import resolve_organisme_from_coti_id
from app.modules.exports.domain.controle_comptable import controler, residu_du_bulletin

pytestmark = pytest.mark.unit


def _organisme(coti):
    return resolve_organisme_from_coti_id(coti.get("coti_id"), str(coti.get("libelle") or ""))


LIGNE = {
    "employee_name": "Salarié Témoin",
    "brut": 2000.0,
    "net_a_payer": 1250.0,
    "pas": 50.0,
    "cotisations_detail": [
        {"coti_id": "csg_deductible", "montant_salarial": 400.0, "montant_patronal": 0.0},
        {"coti_id": "securite_sociale_maladie", "montant_salarial": 0.0, "montant_patronal": 300.0},
    ],
    "elements_hors_brut": [
        {"famille": "acompte_verse", "montant": -300.0},
    ],
}

ECRITURES = [
    {"nature": "brut", "debit": 2000.0, "credit": 0.0},
    {"nature": "net_a_payer", "debit": 0.0, "credit": 1250.0},
    {"nature": "pas", "debit": 0.0, "credit": 50.0},
    {"nature": "charges:URSSAF", "debit": 300.0, "credit": 0.0},
    {"nature": "dettes:URSSAF", "debit": 0.0, "credit": 700.0},
    {"nature": "hors_brut:acompte_verse", "debit": 0.0, "credit": 300.0},
]


class TestResidu:
    def test_bulletin_complet(self):
        assert residu_du_bulletin(LIGNE) == 0.0

    def test_montant_non_classe(self):
        ligne = {**LIGNE, "net_a_payer": 1230.0}
        assert residu_du_bulletin(ligne) == 20.0


class TestControler:
    def test_export_juste(self):
        rapport = controler([LIGNE], ECRITURES, _organisme)
        assert rapport["equilibre"] is True
        assert rapport["complet"] is True
        assert rapport["natures_en_ecart"] == []

    def test_montant_oublie_par_l_export(self):
        ecritures = [e for e in ECRITURES if e["nature"] != "hors_brut:acompte_verse"]
        rapport = controler([LIGNE], ecritures, _organisme)
        assert rapport["equilibre"] is False
        assert rapport["complet"] is False
        assert rapport["natures_en_ecart"] == [
            {"nature": "hors_brut:acompte_verse", "bulletins": -300.0, "export": 0.0, "ecart": 300.0}
        ]

    def test_montant_poste_deux_fois(self):
        ecritures = ECRITURES + [{"nature": "pas", "debit": 0.0, "credit": 50.0}]
        rapport = controler([LIGNE], ecritures, _organisme)
        assert rapport["natures_en_ecart"][0]["nature"] == "pas"
        assert rapport["natures_en_ecart"][0]["ecart"] == -50.0

    def test_bulletin_incoherent_signale(self):
        ligne = {**LIGNE, "net_a_payer": 1250.01}
        rapport = controler([ligne], ECRITURES, _organisme)
        assert rapport["complet"] is False
        assert rapport["bulletins_incoherents"] == [
            {"employee_name": "Salarié Témoin", "residu": -0.01}
        ]
