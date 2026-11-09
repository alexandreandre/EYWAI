"""Prévoyance des cadres : ce que la fiche doit porter (ANI du 17/11/2017, art. 1er).

Audit du 03/11/2026 : deux cadres sans aucune ligne de prévoyance pendant des
mois. La règle se lit sur la fiche, sans base de données.
"""

from __future__ import annotations

import pytest

from app.shared.domain.prevoyance_obligatoire import (
    CODE_CADRE_SANS_LIGNE,
    CODE_CADRE_SANS_PREVOYANCE,
    alerte_minimum_cadre,
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


class TestMinimumCadre:
    """Minimum de 1,50 % de la tranche A, part de santé comprise (R-371)."""

    LIGNES = [{"libelle": "Prévoyance", "patronal": 0.01155, "salarial": 0.0, "base": "brut_plafonne"}]

    def test_sous_le_minimum_sans_sante(self):
        alerte = alerte_minimum_cadre(self.LIGNES, sante_patronale=0.0, tranche_a=4005.0)
        assert alerte["code"] == "prevoyance_cadre_sous_le_minimum"
        assert alerte["critique"] is False and alerte["severity"] == "warning"
        assert "60,08" in alerte["message"]
        assert "46,26" in alerte["message"]

    def test_la_part_de_sante_compte(self):
        assert alerte_minimum_cadre(self.LIGNES, sante_patronale=20.0, tranche_a=4005.0) is None

    def test_exactement_le_minimum(self):
        lignes = [{"patronal": 0.015}]
        assert alerte_minimum_cadre(lignes, sante_patronale=0.0, tranche_a=4005.0) is None

    def test_la_tranche_b_ne_compte_pas(self):
        lignes = [{"patronal": 0.02, "base": "tranche_2"}]
        assert alerte_minimum_cadre(lignes, sante_patronale=0.0, tranche_a=4005.0) is not None

    def test_metallurgie_non_controlee(self):
        assert alerte_minimum_cadre(self.LIGNES, sante_patronale=0.0, tranche_a=4005.0, idcc="3248") is None

    def test_sur_la_fiche_un_cadre_sous_le_minimum(self):
        fiche = {
            "statut": "Cadre",
            "specificites_paie": {"prevoyance": {"adhesion": True, "lignes_specifiques": self.LIGNES}},
        }
        alertes = alertes_prevoyance_de_la_fiche(fiche, plafond_mensuel=4005.0, sante_patronale=lambda: 0.0)
        assert [a["code"] for a in alertes] == ["prevoyance_cadre_sous_le_minimum"]

    def test_sur_la_fiche_sante_illisible_pas_de_fausse_alerte(self):
        fiche = {
            "statut": "Cadre",
            "specificites_paie": {"prevoyance": {"adhesion": True, "lignes_specifiques": self.LIGNES}},
        }
        assert alertes_prevoyance_de_la_fiche(fiche, plafond_mensuel=4005.0, sante_patronale=lambda: None) == []

    def test_sur_la_fiche_sans_plafond_rien(self):
        fiche = {
            "statut": "Cadre",
            "specificites_paie": {"prevoyance": {"adhesion": True, "lignes_specifiques": self.LIGNES}},
        }
        assert alertes_prevoyance_de_la_fiche(fiche) == []

    def test_cadre_a_un_et_demi_rien_a_lire(self):
        lignes = [{"patronal": 0.016}]
        fiche = {"statut": "Cadre", "specificites_paie": {"prevoyance": {"adhesion": True, "lignes_specifiques": lignes}}}
        lectures = []
        alertes = alertes_prevoyance_de_la_fiche(
            fiche, plafond_mensuel=4005.0, sante_patronale=lambda: lectures.append(1) or 0.0
        )
        assert alertes == [] and lectures == []
