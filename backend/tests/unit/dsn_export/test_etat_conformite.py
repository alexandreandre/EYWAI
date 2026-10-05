"""Le message « DSN non déposable » dit la vérité et dit quoi faire.

La liste du 03/08 annonçait comme manquants des blocs produits depuis
(bordereau et versements Urssaf, prévoyance, arrêts, fins de contrat,
affiliations). Le blocage, lui, reste : le lever est une décision d'Alexandre.
"""

import pytest

from app.modules.dsn_export.domain import etat_conformite
from app.modules.dsn_export.domain.etat_conformite import (
    DEPOSABLE,
    anomalie_non_deposable,
    message_non_deposable,
)

pytestmark = pytest.mark.unit


def test_le_blocage_reste_pose():
    assert DEPOSABLE is False
    anomalie = anomalie_non_deposable()
    assert anomalie["severity"] == "blocking"
    assert anomalie["message"] == message_non_deposable()


def test_le_message_interdit_le_depot():
    message = message_non_deposable().lower()
    assert "ne déposez pas" in message
    assert "net-entreprises" in message


def test_ce_qui_est_produit_n_est_plus_annonce_manquant():
    deja_produit = " ".join(etat_conformite.DEJA_PRODUIT).lower()
    for bloc in (
        "cotisations individuelles",
        "bordereau",
        "versements urssaf",
        "prévoyance",
        "affiliations",
        "arrêts",
        "fins de contrat",
    ):
        assert bloc in deja_produit, bloc

    reste = " ".join(etat_conformite.RESTE_AVANT_DEPOT).lower()
    for produit in (
        "cotisations individuelles",
        "affiliation",
        "arrêt",
        "fin de contrat",
        "fins de contrat",
        "salariés sortis",
    ):
        assert produit not in reste, produit
    assert not hasattr(etat_conformite, "BLOCS_MANQUANTS")


def test_le_reste_est_dit():
    reste = " ".join(etat_conformite.RESTE_AVANT_DEPOT).lower()
    # Le builder ne produit pas l'appel trimestriel des organismes
    # complémentaires, ni ce qui n'est sur aucun bulletin.
    assert "trimestriel" in reste
    assert "aucun bulletin" in reste
    assert "dsn-val" in reste


def test_le_message_dit_quoi_faire_en_attendant():
    message = message_non_deposable()
    assert "En attendant" in message
    assert "ancien logiciel" in message
    assert "Support" in message
    for ligne in etat_conformite.DEJA_PRODUIT + etat_conformite.RESTE_AVANT_DEPOT:
        assert ligne in message
