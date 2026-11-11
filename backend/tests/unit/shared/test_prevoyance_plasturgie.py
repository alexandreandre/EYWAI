"""Prévoyance des non-cadres de la plasturgie après trois mois d'ancienneté.

Accord du 29/10/2014 (IDCC 0292, étendu), art. 3 : les salariés non cadres
« ayant une ancienneté d'au moins trois mois dans l'entreprise » ; art. 5 :
0,8 % du brut dont 0,4 % patronal. Audit du 03/11/2026 : un CDD non-cadre
embauché le 02/03 sans prévoyance de juin à septembre.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.shared.domain.prevoyance_obligatoire import (
    CODE_PLASTURGIE_SANS_PREVOYANCE,
    alertes_prevoyance_de_la_fiche,
    anciennete_plasturgie_atteinte,
    dernier_jour_du_mois,
    idcc_de_la_classification,
    prevoyance_manquante,
)

pytestmark = pytest.mark.unit


def _cdd(adhesion=False, **extra):
    fiche = {
        "statut": "Non-Cadre",
        "contract_type": "CDD",
        "hire_date": "2026-03-02",
        "specificites_paie": {"prevoyance": {"adhesion": adhesion}},
        "classification_conventionnelle": {"statut_categoriel": "Non-Cadre", "idcc": "0292"},
    }
    fiche.update(extra)
    return fiche


@pytest.mark.parametrize(
    "mois, attendu",
    [(3, False), (4, False), (5, False), (6, True), (9, True)],
)
def test_trois_mois_d_anciennete_le_02_06(mois, attendu):
    assert anciennete_plasturgie_atteinte(_cdd(), dernier_jour_du_mois(2026, mois)) is attendu


def test_le_cdd_sans_prevoyance_apres_trois_mois_la_manque():
    manque = prevoyance_manquante(_cdd(), idcc="0292", fin_du_mois=date(2026, 6, 30))
    assert manque is not None
    assert manque.code == CODE_PLASTURGIE_SANS_PREVOYANCE
    assert "plasturgie" in manque.fiche


def test_avant_trois_mois_la_loi_n_impose_rien():
    assert prevoyance_manquante(_cdd(), idcc="0292", fin_du_mois=date(2026, 5, 31)) is None


def test_une_fiche_affiliee_ne_manque_de_rien():
    """Non-cadre coché sans ligne : le barème national s'applique, rien ne manque."""
    assert prevoyance_manquante(_cdd(adhesion=True), idcc="0292", fin_du_mois=date(2026, 9, 30)) is None


@pytest.mark.parametrize("idcc", ["3248", "9999", "", None])
def test_hors_plasturgie_rien_n_est_exige_des_non_cadres(idcc):
    assert prevoyance_manquante(_cdd(), idcc=idcc, fin_du_mois=date(2026, 9, 30)) is None


def test_l_idcc_sans_zero_vaut_la_plasturgie():
    assert prevoyance_manquante(_cdd(), idcc="292", fin_du_mois=date(2026, 9, 30)) is not None


def test_la_date_de_reprise_compte_avant_l_embauche():
    fiche = _cdd(hire_date="2026-09-01", seniority_reference_date="2025-02-28")
    assert prevoyance_manquante(fiche, idcc="0292", fin_du_mois=date(2026, 9, 30)) is not None


def test_l_idcc_n_est_lu_que_s_il_compte():
    lu = []

    def lire():
        lu.append(1)
        return "0292"

    assert prevoyance_manquante(_cdd(adhesion=True), idcc=lire, fin_du_mois=date(2026, 9, 30)) is None
    assert prevoyance_manquante(_cdd(), idcc=lire, fin_du_mois=date(2026, 4, 30)) is None
    assert lu == []
    assert prevoyance_manquante(_cdd(), idcc=lire, fin_du_mois=date(2026, 9, 30)) is not None
    assert lu == [1]


def test_un_stagiaire_n_est_pas_un_salarie_de_l_accord():
    fiche = _cdd(contract_type="Stage")
    assert prevoyance_manquante(fiche, idcc="0292", fin_du_mois=date(2026, 9, 30)) is None


def test_sans_mois_seule_la_regle_des_cadres_s_applique():
    assert prevoyance_manquante(_cdd(), idcc="0292") is None


def test_l_idcc_de_la_classification():
    assert idcc_de_la_classification(_cdd()) == "0292"
    assert idcc_de_la_classification({}) == ""


def test_la_fiche_le_dit():
    alertes = alertes_prevoyance_de_la_fiche(_cdd(), idcc="0292", fin_du_mois=date(2026, 11, 30))
    assert [a["code"] for a in alertes] == [CODE_PLASTURGIE_SANS_PREVOYANCE]


def test_l_alerte_du_bulletin_tient_dans_l_ecran_et_n_arrete_rien():
    alerte = prevoyance_manquante(_cdd(), idcc="0292", fin_du_mois=date(2026, 9, 30)).alerte_du_bulletin()
    assert alerte["code"] == CODE_PLASTURGIE_SANS_PREVOYANCE
    assert alerte["message"].startswith("3 mois d'ancienneté, sans prévoyance")
    assert alerte["critique"] is False
    assert len(alerte["message"]) <= 220
