"""La période d'origine d'une régularisation (page client du 10/11/2026, C1).

Une régularisation de cotisation ou d'heures porte, si la gestionnaire la
saisit, le mois de début et le mois de fin de la période qu'elle corrige. La
période s'imprime dans le libellé (« … – 09/2026 » ou « … – 07/2026 à
09/2026 ») et la DSN rattache la régularisation à ses mois d'origine. Sans
période, rien ne change : charge utile, libellé et ligne restent ceux d'hier.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import (
    RegularisationCotisation,
    RegularisationHeures,
    RegularisationInvalide,
    periode_affichee,
)
from app.modules.payslips.domain.corrections import (
    CorrectionsBulletin,
    refus_des_periodes_de_regularisation,
    refus_des_regularisations_heures,
)

pytestmark = pytest.mark.unit


def _chomage(**periode):
    return RegularisationCotisation(
        coti_id="assurance_chomage",
        libelle="Assurance chômage",
        motif="Taux erroné",
        base=100.0,
        taux_patronal=0.04,
        **periode,
    )


def test_periode_affichee_un_mois_ou_une_plage():
    assert periode_affichee("2026-09", None) == "09/2026"
    assert periode_affichee("2026-09", "2026-09") == "09/2026"
    assert periode_affichee("2026-07", "2026-09") == "07/2026 à 09/2026"


def test_sans_periode_la_regularisation_de_cotisation_ne_change_pas():
    regul = _chomage()
    assert "mois_debut" not in regul.charge_utile()
    assert "mois_fin" not in regul.charge_utile()
    ligne = regul.ligne_de_cotisation()
    assert ligne["libelle"] == "Régularisation – Assurance chômage"
    assert "mois_debut" not in ligne["regularisation"]


def test_la_periode_s_imprime_dans_le_libelle_et_se_garde_dans_la_charge_utile():
    regul = _chomage(mois_debut="2026-07", mois_fin="2026-09")
    charge = regul.charge_utile()
    assert charge["mois_debut"] == "2026-07"
    assert charge["mois_fin"] == "2026-09"
    ligne = regul.ligne_de_cotisation()
    assert ligne["libelle"] == "Régularisation – Assurance chômage – 07/2026 à 09/2026"
    assert ligne["regularisation"]["mois_debut"] == "2026-07"
    saisie = regul.saisie_du_mois({"employee_id": "e"})
    assert saisie["name"].endswith("07/2026 à 09/2026")
    assert saisie["correction_ligne"]["mois_fin"] == "2026-09"


def test_un_seul_mois_vaut_debut_et_fin():
    regul = _chomage(mois_debut="2026-09")
    assert regul.mois_fin == "2026-09"
    assert regul.ligne_de_cotisation()["libelle"].endswith(" – 09/2026")


def test_la_periode_se_relit_depuis_la_saisie():
    regul = _chomage(mois_debut="2026-07", mois_fin="2026-09")
    relue = RegularisationCotisation.depuis(regul.charge_utile())
    assert relue == regul


@pytest.mark.parametrize(
    "periode",
    [
        {"mois_debut": "2026-13"},
        {"mois_debut": "2026-09", "mois_fin": "2026-07"},
        {"mois_fin": "2026-09"},
    ],
)
def test_une_periode_illisible_ou_a_l_envers_est_refusee(periode):
    with pytest.raises(RegularisationInvalide):
        _chomage(**periode)


def test_regularisation_d_heures_sur_une_plage():
    regul = RegularisationHeures(
        nature="hs1",
        mois_origine="2026-07",
        mois_fin="2026-09",
        quantite=6.0,
        motif="Heures oubliées",
    )
    assert regul.mois_affiche == "07/2026 à 09/2026"
    assert regul.libelle(0.25) == "Régularisation heures sup 25 % – 07/2026 à 09/2026"
    assert regul.charge_utile()["mois_fin"] == "2026-09"
    assert RegularisationHeures.depuis(regul.charge_utile()) == regul


def test_regularisation_d_heures_sans_fin_ne_change_pas():
    regul = RegularisationHeures(nature="hs1", mois_origine="2026-09", quantite=2.0, motif="Oubli")
    assert "mois_fin" not in regul.charge_utile()
    assert regul.libelle(0.25) == "Régularisation heures sup 25 % – 09/2026"


def test_regularisation_d_heures_fin_avant_debut_refusee():
    with pytest.raises(RegularisationInvalide):
        RegularisationHeures(
            nature="hs1", mois_origine="2026-09", mois_fin="2026-08", quantite=2.0, motif="Oubli"
        )


def test_la_fin_de_periode_ne_depasse_pas_le_bulletin():
    heures = RegularisationHeures(
        nature="hs1", mois_origine="2026-09", mois_fin="2026-11", quantite=2.0, motif="Oubli"
    )
    refus = refus_des_regularisations_heures(
        CorrectionsBulletin(regularisations_heures_ajoutees=(heures,)), 2026, 10, forfait_jours=False
    )
    assert refus and "11/2026" in refus

    cotisation = _chomage(mois_debut="2026-09", mois_fin="2026-11")
    refus = refus_des_periodes_de_regularisation(
        CorrectionsBulletin(regularisations_ajoutees=(cotisation,)), 2026, 10
    )
    assert refus and "postérieure" in refus
    assert (
        refus_des_periodes_de_regularisation(
            CorrectionsBulletin(regularisations_ajoutees=(_chomage(mois_debut="2026-07"),)), 2026, 10
        )
        is None
    )
