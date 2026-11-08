"""Maintien légal : les arrêts des douze mois d'avant se cumulent (D1226-4).

« il est tenu compte des indemnités déjà perçues par l'intéressé durant les douze
mois antérieurs, de telle sorte que si plusieurs absences pour maladie ou accident
ont été indemnisées au cours de ces douze mois, la durée totale d'indemnisation ne
dépasse pas celle applicable » (code du travail, ouvert le 08/11/2026).
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien
from app.modules.payroll.engine.prolongation_arret import jours_legaux_des_12_mois

pytestmark = pytest.mark.unit

DEBUT = date(2026, 9, 1)


def _arr(debut, fin, type_="maladie"):
    return {"debut": debut, "fin": fin, "type": type_}


def _jours(arrets, carence=7, debut=DEBUT, **kw):
    return jours_legaux_des_12_mois(debut, arrets, carence_maladie=carence, plafond=kw.pop("plafond", 60), **kw)


class TestJours:
    def test_aucun_autre_arret(self):
        assert _jours([]) == 0

    def test_un_arret_ancien_compte_apres_sa_carence(self):
        assert _jours([_arr("2026-03-01", "2026-03-20")]) == 13

    def test_hors_des_douze_mois(self):
        assert _jours([_arr("2025-06-01", "2025-06-30")]) == 0

    def test_a_cheval_sur_la_limite(self):
        # Sept. 2025 : le 1er est le début de la fenêtre ; carence comptée au début de l'arrêt.
        assert _jours([_arr("2025-08-20", "2025-09-10")]) == 10

    def test_at_sans_carence(self):
        assert _jours([_arr("2026-03-01", "2026-03-10", "accident_travail")]) == 10

    def test_accident_de_trajet_avec_carence(self):
        assert _jours([_arr("2026-03-01", "2026-03-10", "accident_trajet")]) == 3

    def test_parentalite_ecartee(self):
        assert _jours([_arr("2026-03-01", "2026-05-10", "maternite")]) == 0

    def test_arret_plus_court_que_la_carence(self):
        assert _jours([_arr("2026-03-01", "2026-03-05")]) == 0

    def test_prolongation_une_seule_carence(self):
        arrets = [_arr("2026-03-01", "2026-03-10"), _arr("2026-03-11", "2026-03-20")]
        assert _jours(arrets) == 13

    def test_plafonne_a_la_duree_totale(self):
        assert _jours([_arr("2026-01-01", "2026-05-31")], plafond=60) == 60

    def test_l_arret_en_cours_ne_compte_pas(self):
        assert _jours([_arr("2026-09-01", "2026-09-30"), _arr("2026-10-01", "2026-10-10")]) == 0

    def test_sans_anciennete_a_l_epoque_pas_indemnise(self):
        arrets = [_arr("2026-03-01", "2026-03-20")]
        assert _jours(arrets, date_anciennete=date(2025, 12, 1), min_mois=12) == 0
        assert _jours(arrets, date_anciennete=date(2025, 3, 1), min_mois=12) == 13


def _ctx():
    return SimpleNamespace(
        salaire_base_mensuel=2400.0,
        statut_salarie="Non-Cadre",
        baremes={
            "pss": {"annuel": 48060.0},
            "ij_plafonds": {"maladie": 42.97, "at_mp": 240.49, "at_mp_majoree": 320.66},
        },
        contrat={"contrat": {"date_entree": "2021-03-01", "statut": "Non-Cadre"}},
    )


REGLAGE = {
    "apply_legal_maintenance": True,
    "min_seniority_months": 12,
    "employer_waiting_days": 7,
    "no_seniority_condition": False,
}


def _maintien(arrets_connus):
    arret = {
        "arret_type": "maladie",
        "date_debut": "2026-09-01",
        "date_fin": "2026-09-30",
        "subrogation_active": True,
        "salaire_periode_reelle": 0.0,
        "arrets_connus": arrets_connus,
    }
    return calculer_maintien(
        contexte=_ctx(),
        arret=arret,
        settings=REGLAGE,
        date_debut_periode=date(2026, 9, 1),
        date_fin_periode=date(2026, 9, 30),
    )


def _cible(res):
    return res["maintien"]["maintien_cible"]


class TestAuCalcul:
    def test_sans_autre_arret(self):
        res = _maintien([])
        assert _cible(res) > 0
        assert res["maintien"]["jours_legaux_des_12_mois"] == 0

    def test_les_jours_deja_indemnises_baissent_le_taux(self):
        # Ancienneté de 5 ans : 40 j à 90 %, puis 40 j à 66,66 %. 30 j déjà pris : 23 j à 90 % puis 0
        sans, avec = _maintien([]), _maintien([_arr("2026-02-01", "2026-03-09")])
        assert avec["maintien"]["jours_legaux_des_12_mois"] == 30
        assert _cible(avec) <= _cible(sans)

    def test_droits_epuises_plus_rien(self):
        res = _maintien([_arr("2026-01-01", "2026-06-30")])
        assert _cible(res) == 0.0

    def test_l_alerte_le_dit(self):
        res = _maintien([_arr("2026-02-01", "2026-03-09")])
        assert any("douze mois" in a for a in res["alertes"])
