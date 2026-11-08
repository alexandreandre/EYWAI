"""Une réduction générale corrigée au-delà du cumul se refuse avant d'écrire.

Sinon la saisie reste écrite, le moteur la refuse à chaque recalcul, et le
bulletin reste bloqué sans que personne puisse la retirer.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import (
    CorrectionDeLigne,
    RegularisationCotisation,
)
from app.modules.payslips.domain.corrections import (
    CorrectionsBulletin,
    refus_de_la_reduction_generale,
)

pytestmark = pytest.mark.unit

RG = "Réduction générale de cotisations patronales"
CODE_RG = "cotisation:reduction_generale"


def _bulletin(montant=-300.0, cumul=-1300.0, **ligne):
    return {
        "cumuls": {"cumuls": {"reduction_generale_patronale": cumul}},
        "cotisations_officielles": [
            {
                "lignes": [
                    {
                        "coti_id": "reduction_generale",
                        "libelle": RG,
                        "montant_salarial": 0.0,
                        "montant_patronal": montant,
                        **ligne,
                    }
                ]
            }
        ],
    }


def _correction(montant):
    return CorrectionDeLigne(ligne=CODE_RG, libelle=RG, motif="Erreur", montant_patronal=montant)


def _regul(montant):
    return RegularisationCotisation(
        coti_id="reduction_generale", libelle=RG, motif="Erreur", montant_patronal=montant
    )


def test_une_correction_au_dela_du_cumul_est_refusee():
    # 1 000 € déjà appliqués depuis janvier : +100 000 € rendrait l'année négative.
    refus = refus_de_la_reduction_generale(
        CorrectionsBulletin(corrections_ajoutees=(_correction(100000.0),)), _bulletin()
    )
    assert refus and "réduction générale" in refus.lower()


def test_une_correction_dans_le_cumul_passe():
    assert (
        refus_de_la_reduction_generale(
            CorrectionsBulletin(corrections_ajoutees=(_correction(-250.0),)), _bulletin()
        )
        is None
    )


def test_une_correction_qui_annule_tout_le_cumul_passe_au_centime():
    assert (
        refus_de_la_reduction_generale(
            CorrectionsBulletin(corrections_ajoutees=(_correction(1000.0),)), _bulletin()
        )
        is None
    )


def test_une_regularisation_au_dela_du_cumul_est_refusee():
    refus = refus_de_la_reduction_generale(
        CorrectionsBulletin(regularisations_ajoutees=(_regul(1500.0),)), _bulletin()
    )
    assert refus and "réduction générale" in refus.lower()


def test_une_regularisation_dans_le_cumul_passe():
    assert (
        refus_de_la_reduction_generale(
            CorrectionsBulletin(regularisations_ajoutees=(_regul(500.0),)), _bulletin()
        )
        is None
    )


def test_sans_cumul_lisible_le_moteur_reste_seul_juge():
    donnees = _bulletin()
    del donnees["cumuls"]
    assert (
        refus_de_la_reduction_generale(
            CorrectionsBulletin(corrections_ajoutees=(_correction(100000.0),)), donnees
        )
        is None
    )


def test_une_autre_ligne_n_est_pas_concernee():
    autre = CorrectionDeLigne(
        ligne="cotisation:fnal", libelle="FNAL", motif="Erreur", montant_patronal=100000.0
    )
    assert (
        refus_de_la_reduction_generale(CorrectionsBulletin(corrections_ajoutees=(autre,)), _bulletin())
        is None
    )
