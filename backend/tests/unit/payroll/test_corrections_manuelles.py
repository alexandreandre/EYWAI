"""La régularisation de cotisation, saisie à la main depuis le bulletin.

Une ligne rattachée à l'organisme de la ligne qu'elle régularise, calculée
comme le moteur (base × taux, au centime), rejouée à chaque calcul.
"""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.corrections_manuelles import (
    CLE_REGULARISATIONS_COTISATION,
    RegularisationCotisation,
    RegularisationInvalide,
    ajouter_regularisations,
    est_regularisation_cotisation,
    mentions_des_regularisations,
    ranger_regularisation,
    regularisations_du_bulletin,
)

pytestmark = pytest.mark.unit

PERIODE = {"employee_id": "e", "company_id": "c", "year": 2026, "month": 10}


def _par_base(**k):
    donnees = dict(
        coti_id="securite_sociale_maladie",
        libelle="Sécurité sociale - Maladie",
        motif="Base de septembre oubliée",
        base=100.0,
        taux_patronal=0.07,
    )
    donnees.update(k)
    return RegularisationCotisation(**donnees)


def test_les_montants_suivent_la_base_et_le_taux_au_centime():
    r = _par_base(base=33.33, taux_salarial=0.069, taux_patronal=0.0855)
    assert r.montants() == (2.30, 2.85)


def test_une_cotisation_au_forfait_se_regularise_par_son_montant():
    r = RegularisationCotisation(
        coti_id="mutuelle",
        libelle="Mutuelle",
        motif="Tarif 2026",
        montant_salarial=-4.1,
        montant_patronal=8.3,
    )
    assert r.montants() == (-4.10, 8.30)


@pytest.mark.parametrize(
    "champs",
    [
        {"motif": "  "},
        {"coti_id": ""},
        {"base": None},
        {"montant_patronal": 3.0},
        {"taux_patronal": None, "taux_salarial": None},
    ],
)
def test_une_regularisation_incomplete_ou_ambigue_est_refusee(champs):
    with pytest.raises(RegularisationInvalide):
        _par_base(**champs)


def test_la_ligne_garde_l_organisme_et_reprend_le_libelle():
    ligne = _par_base(saisie_id="s1").ligne_de_cotisation()
    assert ligne["coti_id"] == "securite_sociale_maladie"
    assert ligne["libelle"] == "Régularisation – Sécurité sociale - Maladie"
    assert ligne["montant_patronal"] == 7.0 and ligne["montant_salarial"] == 0.0
    assert ligne["explication"] == "Régularisation saisie à la main : Base de septembre oubliée"
    assert ligne["regularisation"]["saisie_id"] == "s1"
    assert ligne["rubrique"]


def test_la_saisie_du_mois_porte_la_charge_et_aucun_montant():
    saisie = _par_base().saisie_du_mois(PERIODE)
    assert saisie["amount"] == 0
    assert saisie["name"] == "Régularisation – Sécurité sociale - Maladie"
    assert saisie["correction_ligne"]["type"] == "regularisation_cotisation"
    assert saisie["correction_ligne"]["base"] == 100.0
    assert est_regularisation_cotisation(saisie)
    assert not est_regularisation_cotisation({"name": "Prime", "correction_ligne": None})


def test_le_generateur_range_la_regularisation_a_part_des_primes():
    saisies_data = {"primes": []}
    saisie = {**_par_base().saisie_du_mois(PERIODE), "id": "s1"}
    assert ranger_regularisation(saisie, saisies_data) is True
    assert saisies_data["primes"] == []
    assert saisies_data[CLE_REGULARISATIONS_COTISATION][0]["saisie_id"] == "s1"
    assert ranger_regularisation({"name": "Prime", "amount": 10}, saisies_data) is False


def test_poser_les_regularisations_ajoute_les_lignes_et_le_salarial():
    lignes = [{"coti_id": "x", "montant_salarial": 10.0, "montant_patronal": 0.0}]
    saisie_du_mois = {
        CLE_REGULARISATIONS_COTISATION: [
            {**_par_base(taux_salarial=0.1).charge_utile(), "saisie_id": "s1"},
            {
                **RegularisationCotisation(
                    coti_id="reduction_generale",
                    libelle="Réduction générale de cotisations patronales",
                    motif="Écart de juillet",
                    montant_patronal=-12.5,
                ).charge_utile(),
                "saisie_id": "s2",
            },
        ]
    }
    effet = ajouter_regularisations(lignes, 10.0, saisie_du_mois)
    assert len(lignes) == 3
    assert effet.total_salarial == 20.0
    assert effet.reduction_generale == -12.5


def test_sans_regularisation_rien_ne_bouge():
    lignes = [{"coti_id": "x", "montant_salarial": 10.0}]
    effet = ajouter_regularisations(lignes, 10.0, {})
    assert lignes == [{"coti_id": "x", "montant_salarial": 10.0}]
    assert effet.total_salarial == 10.0 and effet.reduction_generale == 0.0


def test_un_bulletin_dit_ses_regularisations_et_ses_mentions():
    ligne = _par_base(saisie_id="s1").ligne_de_cotisation()
    payslip_data = {"cotisations_officielles": [{"code": "sante", "lignes": [{"coti_id": "y"}, ligne]}]}
    trouvees = regularisations_du_bulletin(payslip_data)
    assert list(trouvees) == ["s1"]
    assert trouvees["s1"].base == 100.0
    assert mentions_des_regularisations(payslip_data) == [
        "Régularisation saisie à la main — Sécurité sociale - Maladie : Base de septembre oubliée"
    ]
