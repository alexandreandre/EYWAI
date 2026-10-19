"""Impact net d'un arrêt dans la simulation (relevé du tournage F.3, 19/10/2026).

La simulation affichait « Impact net salarié −2 142,19 € » pour 14 jours d'arrêt
subrogé sur un brut de 2 200 € : elle retirait tout le salaire du mois du seul
maintien employeur. Un arrêt ne fait perdre que ses jours ouvrés, valorisés comme
sur le bulletin ; le salarié touche le maintien et les IJSS (nettes de leur
CSG/CRDS) ; le net se compare, mois par mois, avec et sans l'arrêt.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.application.simulation_arret_maladie import (
    impact_net_de_l_arret,
    salaire_perdu_sur_la_periode,
)
from app.modules.payroll.engine.calcul_brut import _get_salaire_horaire_base
from app.modules.payroll.engine.calcul_brut_forfait import _diviseur_jour_absence
from app.modules.payroll.engine.ijss_bulletin import compute_ijss_csg_lines
from app.modules.payroll.engine.maintien_salaire_service import calculer_maintien

from .helpers import build_test_contexte

pytestmark = pytest.mark.unit

REGLAGES = {"apply_legal_maintenance": True}


def _arret(debut: date, fin: date) -> dict:
    return {
        "arret_type": "maladie_simple",
        "date_debut": debut.isoformat(),
        "date_fin": fin.isoformat(),
        "subrogation_active": True,
        "nombre_enfants": 0,
        "is_temps_partiel": False,
        "quotite_temps_partiel": 1.0,
        "historique_arrets_annee": [],
        "date_dernier_arret": None,
        "salaire_periode_reelle": 0.0,
    }


def test_un_arret_ne_fait_perdre_que_ses_jours_ouvres_a_la_reference_legale():
    ctx = build_test_contexte(salaire_base=2200.0, duree_hebdo=35.0)
    # Du lundi 5 au dimanche 18 octobre 2026 : 10 jours ouvrés.
    perdu = salaire_perdu_sur_la_periode(ctx, date(2026, 10, 5), date(2026, 10, 18))
    assert perdu == round(10 * 7.0 * _get_salaire_horaire_base(ctx, 35.0), 2)
    assert 1000 < perdu < 1030  # loin des 2 200 € du mois entier


def test_au_forfait_jours_un_jour_perdu_vaut_le_salaire_au_diviseur_d_absence():
    ctx = build_test_contexte(salaire_base=3900.0, statut="Cadre")
    ctx.contrat["contrat"]["is_forfait_jour"] = True
    perdu = salaire_perdu_sur_la_periode(ctx, date(2026, 10, 5), date(2026, 10, 9))
    assert perdu == round(5 * 3900.0 / _diviseur_jour_absence(ctx), 2)


def test_l_impact_compare_deux_nets_et_ajoute_les_ijss_nettes():
    ctx = build_test_contexte(salaire_base=2200.0, duree_hebdo=35.0)
    debut, fin = date(2026, 10, 5), date(2026, 10, 18)
    arret = _arret(debut, fin)
    net = lambda brut, annee, mois: round(0.78 * brut, 2)  # noqa: E731

    mois = impact_net_de_l_arret(ctx, arret, REGLAGES, debut, fin, net)

    attendu = calculer_maintien(arret, ctx, REGLAGES, debut, fin)
    maintien = attendu["maintien"]["maintien_verse"]
    ijss = attendu["ijss"]["ijss_theorique"]
    perdu = salaire_perdu_sur_la_periode(ctx, debut, fin)
    ijss_nettes = compute_ijss_csg_lines(ijss, ctx.baremes.get("maladie"))[2]
    assert len(mois) == 1
    assert mois[0].impact == round(net(2200 - perdu + maintien, 2026, 10) - net(2200, 2026, 10) + ijss_nettes, 2)
    # Le salarié perd moins que le salaire des jours d'arrêt, et bien moins que son mois.
    assert -perdu < mois[0].impact < 0


def test_un_arret_a_cheval_sur_deux_mois_se_calcule_mois_par_mois():
    ctx = build_test_contexte(salaire_base=2200.0, duree_hebdo=35.0)
    debut, fin = date(2026, 10, 19), date(2026, 11, 6)
    appels = []

    def net(brut, annee, mois):
        appels.append((annee, mois))
        return round(0.78 * brut, 2)

    mois = impact_net_de_l_arret(ctx, _arret(debut, fin), REGLAGES, debut, fin, net)
    assert [(m.annee, m.mois) for m in mois] == [(2026, 10), (2026, 11)]
    assert sorted(set(appels)) == [(2026, 10), (2026, 11)]
    assert mois[0].salaire_perdu == salaire_perdu_sur_la_periode(ctx, date(2026, 10, 19), date(2026, 10, 31))
    assert mois[1].salaire_perdu == salaire_perdu_sur_la_periode(ctx, date(2026, 11, 1), date(2026, 11, 6))
