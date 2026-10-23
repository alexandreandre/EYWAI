"""Réduction générale corrigée par son montant, impôt par le taux du mois ; leurs
cumuls enregistrent ce qui a été appliqué et prélevé (spec § 5 et § 6)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from app.modules.payroll.engine.calcul_net import calculer_net_et_impot
from app.modules.payroll.engine.calcul_reduction_generale import calculer_reduction_generale
from app.modules.payroll.engine.corrections_manuelles import CorrectionDeLigne, JournalDesCorrections

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

RG = "Réduction générale de cotisations patronales"


def _contexte(*corrections, cumuls=None):
    contexte = build_test_contexte(taux_pas=5.2, cumuls=cumuls)
    contexte.year, contexte.month = 2026, 4
    if corrections:
        contexte.corrections_du_mois = JournalDesCorrections(list(corrections))
    return contexte


def _c(code, libelle, **champs):
    return CorrectionDeLigne(ligne=code, libelle=libelle, motif="Test", saisie_id="s1", **champs)


def test_sans_correction_la_reduction_est_identique():
    assert calculer_reduction_generale(_contexte(), 2500.0, 155.67) == calculer_reduction_generale(
        _contexte(_c("brut:salaire_base", "Salaire de base", base=1.0)), 2500.0, 155.67
    )


def test_la_reduction_corrigee_enregistre_ce_qui_est_applique():
    reference = calculer_reduction_generale(_contexte(cumuls={"reduction_generale_patronale": -1000.0}), 2500.0, 155.67)
    contexte = _contexte(
        _c("cotisation:reduction_generale", RG, montant_patronal=-300.0),
        cumuls={"reduction_generale_patronale": -1000.0},
    )
    ligne = calculer_reduction_generale(contexte, 2500.0, 155.67)
    assert ligne["montant_patronal"] == -300.0
    assert ligne["valeur_calculee"]["montant_patronal"] == reference["montant_patronal"]
    assert ligne["valeur_cumulative_a_enregistrer"] == 1300.0
    assert ligne["smic_reference_mois"] == reference["smic_reference_mois"]


def test_le_cumul_de_la_reduction_et_de_l_impot_suit_la_correction(tmp_path):
    contexte = SimpleNamespace(
        cumuls={"cumuls": {"reduction_generale_patronale": -1000.0, "brut_total": 7500.0,
                           "impot_preleve_a_la_source": 300.0}, "periode": {}},
        company_id=None,
        year=2026,
    )
    ligne_rg = {"coti_id": "reduction_generale", "montant_patronal": -300.0, "valeur_cumulative_a_enregistrer": 1300.0}
    mettre_a_jour_cumuls(
        contexte, 2500.0, 0.0, {"net_imposable": 2000.0, "montant_impot_pas": 150.0}, ligne_rg, 4, 0.0, 0.0, tmp_path
    )
    cumuls = json.loads((tmp_path / "cumuls" / "04.json").read_text(encoding="utf-8"))["cumuls"]
    assert cumuls["reduction_generale_patronale"] == -1300.0
    assert cumuls["impot_preleve_a_la_source"] == 450.0


def _nets(contexte):
    lignes, total = calculer_cotisations(contexte, 2500.0, 82.42, 4.0)
    return calculer_net_et_impot(contexte, 2500.0, lignes, total, [], 82.42, 0.0, [])


def test_sans_correction_l_impot_est_identique_et_ne_dit_rien_de_plus():
    reference = _nets(_contexte())
    assert "correction_impot" not in reference
    assert _nets(_contexte(_c("brut:salaire_base", "Salaire de base", base=1.0))) == reference


def test_le_taux_d_impot_du_mois_corrige_fait_suivre_le_montant_et_le_net():
    reference = _nets(_contexte())
    nets = _nets(_contexte(_c("impot", "Impôt sur le revenu prélevé à la source", taux=7.5)))
    attendu = round(reference["base_pas"] * (7.5 / 100.0), 2)
    assert nets["taux_pas_applique"] == 7.5
    assert nets["montant_impot_pas"] == attendu
    assert nets["net_a_payer"] == pytest.approx(reference["net_a_payer"] - (attendu - reference["montant_impot_pas"]), abs=0.005)
    assert nets["correction_impot"]["valeur_calculee"] == {
        "taux": reference["taux_pas_applique"],
        "montant": reference["montant_impot_pas"],
    }
