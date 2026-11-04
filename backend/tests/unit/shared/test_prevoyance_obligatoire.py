"""Prévoyance des cadres : ce que la fiche doit porter (ANI du 17/11/2017, art. 1er).

Audit du 03/11/2026 : deux cadres sans aucune ligne de prévoyance pendant des
mois. La règle se lit sur la fiche, sans base de données.
"""

from __future__ import annotations

import pytest

from app.shared.domain.prevoyance_obligatoire import (
    CODE_CADRE_SANS_LIGNE,
    CODE_CADRE_SANS_PREVOYANCE,
    alertes_prevoyance_de_la_fiche,
    cadre_de_la_prevoyance,
    prevoyance_manquante,
)

pytestmark = pytest.mark.unit

_LIGNE = {"libelle": "Prévoyance cadre TA", "base": "brut_plafonne", "salarial": 0.0, "patronal": 0.015}


def _fiche(statut="Cadre", prevoyance=None, **extra):
    fiche = {
        "statut": statut,
        "contract_type": "CDI",
        "specificites_paie": {"prevoyance": prevoyance if prevoyance is not None else {"adhesion": False}},
        "classification_conventionnelle": {"statut_categoriel": "Cadre"},
    }
    fiche.update(extra)
    return fiche


def test_un_cadre_sans_adhesion_manque_sa_prevoyance():
    manque = prevoyance_manquante(_fiche())
    assert manque is not None
    assert manque.code == CODE_CADRE_SANS_PREVOYANCE
    assert "Adhésion prévoyance" in manque.fiche


def test_un_cadre_sans_specificites_manque_sa_prevoyance():
    assert prevoyance_manquante({"statut": "Cadre"}).code == CODE_CADRE_SANS_PREVOYANCE


def test_un_cadre_coche_sans_ligne_manque_ses_lignes():
    manque = prevoyance_manquante(_fiche(prevoyance={"adhesion": True, "lignes_specifiques": []}))
    assert manque is not None
    assert manque.code == CODE_CADRE_SANS_LIGNE


def test_un_cadre_couvert_ne_manque_de_rien():
    assert prevoyance_manquante(_fiche(prevoyance={"adhesion": True, "lignes_specifiques": [_LIGNE]})) is None
    assert alertes_prevoyance_de_la_fiche(
        _fiche(prevoyance={"adhesion": True, "lignes_specifiques": [_LIGNE]})
    ) == []


@pytest.mark.parametrize("statut", ["Non-Cadre", "non cadre", "", None])
def test_un_non_cadre_ne_releve_pas_de_la_prevoyance_des_cadres(statut):
    assert prevoyance_manquante(_fiche(statut=statut)) is None


def test_cadre_au_forfait_jour_mais_non_cadre_a_la_classification():
    """Forfait jours non-cadre de la plasturgie : « Cadre » en paie, non-cadre en DSN,
    comme pour l'APEC."""
    fiche = _fiche(
        statut="Cadre au forfait jour",
        classification_conventionnelle={"statut_categoriel": "Non-Cadre"},
    )
    assert not cadre_de_la_prevoyance(fiche)
    assert prevoyance_manquante(fiche) is None


def test_un_cadre_au_forfait_jour_reste_cadre():
    assert prevoyance_manquante(_fiche(statut="Cadre au forfait jour")).code == CODE_CADRE_SANS_PREVOYANCE


def test_un_mandataire_social_n_est_pas_un_salarie_de_l_accord():
    assert prevoyance_manquante(_fiche(specificites_paie={"is_mandataire": True})) is None
    assert prevoyance_manquante(_fiche(contract_type="Mandataire social")) is None


def test_la_fiche_porte_une_alerte_code_et_message():
    alertes = alertes_prevoyance_de_la_fiche(_fiche())
    assert alertes == [{"code": CODE_CADRE_SANS_PREVOYANCE, "message": prevoyance_manquante(_fiche()).fiche}]


@pytest.mark.parametrize(
    "prevoyance", [{"adhesion": False}, {"adhesion": True, "lignes_specifiques": []}]
)
def test_le_refus_nomme_la_personne_et_tient_dans_l_ecran(prevoyance):
    """L'écran coupe un message du serveur au-delà de 220 signes : la phrase entière
    doit passer, prénom long compris."""
    refus = prevoyance_manquante(_fiche(prevoyance=prevoyance)).refus_pour("Marie-Christine")
    assert refus.startswith("Bulletin non généré : Marie-Christine est cadre")
    assert refus.endswith("puis relancez.")
    assert len(refus) <= 220
