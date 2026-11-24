"""Prêts et saisies de l'ancien logiciel : ce que Martine doit signaler."""

import pytest

from app.modules.payroll.domain.retenues_reprises import (
    RetenueReprise,
    message_retenue,
    retenues_du_bulletin_repris,
    saisie_posee_dans_martine,
)

pytestmark = pytest.mark.unit


def test_lit_un_pret_dans_les_primes_non_soumises_negatives():
    data = {"primes_non_soumises": [
        {"libelle": "PRIME PARTAGE DE LA VALEUR", "montant": 100.0},
        {"libelle": "Contrat de prêt ESSAI", "montant": -250.0},
        {"libelle": "Remboursement pret ESSAI", "montant": -225.0},
    ]}
    assert retenues_du_bulletin_repris(data) == [
        RetenueReprise("pret", "Contrat de prêt ESSAI", 250.0),
        RetenueReprise("pret", "Remboursement pret ESSAI", 225.0),
    ]


@pytest.mark.parametrize("libelle", ["Saisie SGC CHAMBERY", "Saisie sur salaire", "ATD SIP AMIENS", "saisie Trésorie"])
def test_lit_une_saisie_sur_le_net(libelle):
    assert retenues_du_bulletin_repris({"retenues_sur_net": [{"libelle": libelle, "montant": 150.0}]}) == [
        RetenueReprise("saisie", libelle, 150.0)
    ]


@pytest.mark.parametrize("libelle", ["Acompte 09/2026", "Virement 30/09", "Report NAP négatif"])
def test_ne_prend_ni_acompte_ni_virement(libelle):
    assert retenues_du_bulletin_repris({"retenues_sur_net": [{"libelle": libelle, "montant": 150.0}]}) == []


def test_un_remboursement_de_saisie_en_negatif_n_est_pas_une_retenue():
    assert retenues_du_bulletin_repris({"retenues_sur_net": [{"libelle": "Saisie trésorie", "montant": -246.02}]}) == []


def test_bulletin_vide():
    assert retenues_du_bulletin_repris(None) == []


def test_le_message_dit_quoi_faire():
    m = message_retenue(RetenueReprise("saisie", "ATD SIP AMIENS", 150.0), "septembre 2026")
    assert "150,00 €" in m and "aucune saisie ouverte" in m


def test_une_saisie_active_est_posee():
    assert saisie_posee_dans_martine({"status": "active", "montant_total": None})


def test_une_saisie_terminee_avec_un_montant_total_est_posee():
    """Dette soldée dans Martine (arrêt automatique) : rien à rappeler."""
    assert saisie_posee_dans_martine({"status": "closed", "montant_total": 1200})


@pytest.mark.parametrize(
    "saisie",
    [
        {"status": "closed", "montant_total": None},
        {"status": "suspended", "montant_total": 1200},
        {"status": "suspended"},
    ],
)
def test_les_autres_saisies_ne_comptent_pas_comme_avant(saisie):
    assert not saisie_posee_dans_martine(saisie)
