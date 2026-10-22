"""Une régularisation de cotisation se déclare avec sa ligne d'origine.

Le montant et l'assiette s'additionnent. Le taux reste celui de la cotisation.
"""

from __future__ import annotations

import pytest

from app.modules.dsn_export.domain.cotisation_mapping import build_bases_and_cotisations
from app.modules.payroll.engine.corrections_manuelles import RegularisationCotisation

pytestmark = pytest.mark.unit


def _maladie(base):
    return {
        "coti_id": "securite_sociale_maladie",
        "libelle": "Sécurité sociale - Maladie",
        "base": base,
        "taux_salarial": None,
        "taux_patronal": 0.07,
        "montant_salarial": 0.0,
        "montant_patronal": round(base * 0.07, 2),
    }


def _cotisations(lignes):
    _, cotisations, _ = build_bases_and_cotisations(
        lignes, brut=2000.0, period_start="2026-10-01", period_end="2026-10-31"
    )
    return cotisations


def _par_code(cotisations, code):
    trouvees = [c for c in cotisations if c.code == code]
    assert len(trouvees) == 1, trouvees
    return trouvees[0]


def test_la_regularisation_ajoute_son_montant_et_son_assiette_et_garde_le_taux():
    regul = RegularisationCotisation(
        coti_id="securite_sociale_maladie",
        libelle="Sécurité sociale - Maladie",
        motif="Base oubliée",
        base=100.0,
        taux_patronal=0.07,
    ).ligne_de_cotisation()
    sans = _par_code(_cotisations([_maladie(2000.0)]), "075")
    avec = _par_code(_cotisations([_maladie(2000.0), regul]), "075")
    assert avec.montant_patronal == pytest.approx(sans.montant_patronal + 7.0, abs=0.001)
    assert avec.montant_assiette == pytest.approx(sans.montant_assiette + 100.0, abs=0.001)
    assert avec.rubriques.get("S21.G00.81.007") == sans.rubriques.get("S21.G00.81.007")


def test_sans_regularisation_la_dsn_ne_change_pas():
    assert _cotisations([_maladie(2000.0)]) == _cotisations([_maladie(2000.0)])


def test_une_regularisation_agirc_redéclare_la_part_patronale():
    """Le code 131 porte le total, le 142 redéclare la part patronale."""
    ligne = {
        "coti_id": "retraite_comp_t1",
        "libelle": "Retraite complémentaire tranche 1",
        "base": 2000.0,
        "taux_salarial": 0.0401,
        "taux_patronal": 0.0601,
        "montant_salarial": 80.2,
        "montant_patronal": 120.2,
    }
    regul = RegularisationCotisation(
        coti_id="retraite_comp_t1",
        libelle="Retraite complémentaire tranche 1",
        motif="Base oubliée",
        base=10.0,
        taux_salarial=0.0401,
        taux_patronal=0.0601,
    ).ligne_de_cotisation()
    salarial, patronal = RegularisationCotisation(
        coti_id="retraite_comp_t1",
        libelle="Retraite complémentaire tranche 1",
        motif="Base oubliée",
        base=10.0,
        taux_salarial=0.0401,
        taux_patronal=0.0601,
    ).montants()

    def par_code(lignes):
        return {c.code: c.montant_patronal for c in _cotisations(lignes)}

    avant, apres = par_code([ligne]), par_code([ligne, regul])
    assert round(apres["131"] - avant["131"], 2) == round(salarial + patronal, 2)
    assert round(apres["142"] - avant["142"], 2) == round(patronal, 2)


def test_une_exoneration_apprenti_sans_code_dsn_reste_hors_de_la_declaration():
    ligne = {
        "coti_id": "exoneration_apprenti_salariale",
        "libelle": "Exonération cotisations salariales apprenti",
        "base": 1000.0,
        "montant_salarial": -50.0,
        "montant_patronal": 0.0,
    }
    regul = RegularisationCotisation(
        coti_id="exoneration_apprenti_salariale",
        libelle="Exonération cotisations salariales apprenti",
        motif="Plafond du mois",
        montant_salarial=-10.0,
    ).ligne_de_cotisation()
    assert _cotisations([ligne, regul]) == _cotisations([ligne])
