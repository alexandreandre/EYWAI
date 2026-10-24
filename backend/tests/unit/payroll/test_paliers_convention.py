"""Plan conventionnel des jours d'arrêt, barème de la plasturgie (pur).

Carence, paliers par arrêt, limite par arrêt et par année civile, ancienneté
au début de l'arrêt (conception du 24/10/2026). Initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.domain.baremes_maintien import PLASTURGIE
from app.modules.payroll.engine.paliers_convention import (
    RAISON_ACCIDENT,
    RAISON_ALD,
    RAISON_CADRE,
    RAISON_CARENCE,
    RAISON_PREMIER_ARRET,
    RAISON_RELIQUAT,
    ArretDuPlan,
    arrets_pour_le_plan,
    plan_conventionnel,
)

pytestmark = pytest.mark.unit

D = date.fromisoformat


def _arret(debut, fin, type_arret="maladie_simple"):
    return ArretDuPlan(D(debut), D(fin), type_arret)


def _plan(*arrets, cadre=False, entree="2015-01-01"):
    return plan_conventionnel(list(arrets), bareme=PLASTURGIE, est_cadre=cadre, date_anciennete=D(entree))


def _jours_a(plan, taux):
    return sorted(j for j, t in plan.taux_par_jour.items() if t == taux)


def _bornes(jours):
    return (jours[0], jours[-1], len(jours)) if jours else None


def test_s_g_2026_cent_pour_cent_jusqu_au_02_07_puis_75_jusqu_au_15_09():
    """Non-cadre, 22 ans d'ancienneté, premier arrêt de 2026 du 04/05, prolongé jusqu'au 12/10."""
    plan = _plan(
        _arret("2026-05-04", "2026-05-31"), _arret("2026-06-01", "2026-06-30"),
        _arret("2026-07-01", "2026-07-31"), _arret("2026-08-01", "2026-08-31"),
        _arret("2026-09-01", "2026-09-30"), _arret("2026-10-02", "2026-10-12"),
        entree="2003-07-15",
    )
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-05-04"), D("2026-07-02"), 60)
    assert _bornes(_jours_a(plan, 0.75)) == (D("2026-07-03"), D("2026-09-15"), 75)
    (arret,) = plan.arrets  # le 02/10 prolonge (un jour de reprise)
    assert arret.carence_jours == 0 and arret.raison_carence == RAISON_PREMIER_ARRET
    assert arret.bascules == [(D("2026-05-04"), 1.0), (D("2026-07-03"), 0.75)]
    assert arret.limite_atteinte == D("2026-09-15")
    assert D("2026-10-05") not in plan.taux_par_jour


def test_un_deuxieme_arret_de_l_annee_a_trois_jours_de_carence():
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-13"))
    premier, second = plan.arrets
    assert (premier.carence_jours, premier.raison_carence) == (0, RAISON_PREMIER_ARRET)
    assert _bornes([j for j in plan.taux_par_jour if j.month == 2]) == (D("2026-02-02"), D("2026-02-06"), 5)
    assert (second.carence_jours, second.raison_carence) == (3, RAISON_CARENCE)
    assert second.jours_de_carence == (D("2026-03-02"), D("2026-03-03"), D("2026-03-04"))
    assert _bornes(sorted(j for j in plan.taux_par_jour if j.month == 3)) == (
        D("2026-03-05"), D("2026-03-13"), 9,
    )


def test_un_premier_arret_de_deux_jours_donne_deux_jours_de_carence_au_suivant():
    plan = _plan(
        _arret("2026-02-02", "2026-02-03"),
        _arret("2026-03-02", "2026-03-13"),
        _arret("2026-04-06", "2026-04-17"),
    )
    assert [(a.carence_jours, a.raison_carence) for a in plan.arrets] == [
        (0, RAISON_PREMIER_ARRET), (2, RAISON_RELIQUAT), (3, RAISON_CARENCE),
    ]


def test_la_carence_repart_avec_l_annee_civile():
    plan = _plan(_arret("2025-11-03", "2025-11-07"), _arret("2026-01-05", "2026-01-09"))
    assert [a.raison_carence for a in plan.arrets] == [RAISON_PREMIER_ARRET, RAISON_PREMIER_ARRET]


@pytest.mark.parametrize(
    "type_arret, raison",
    [("ald", RAISON_ALD), ("accident_travail", RAISON_ACCIDENT),
     ("maladie_professionnelle", RAISON_ACCIDENT), ("accident_trajet", RAISON_ACCIDENT)],
)
def test_pas_de_carence_en_ald_ni_en_accident(type_arret, raison):
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-13", type_arret))
    assert (plan.arrets[1].carence_jours, plan.arrets[1].raison_carence) == (0, raison)
    assert D("2026-03-02") in plan.taux_par_jour


def test_une_prolongation_apres_deux_jours_de_reprise_reste_le_meme_arret():
    plan = _plan(
        _arret("2026-02-02", "2026-02-04"),
        _arret("2026-03-02", "2026-03-06"), _arret("2026-03-09", "2026-03-13"),
    )
    assert len(plan.arrets) == 2
    assert plan.arrets[1].carence_jours == 3
    mars = sorted(j for j in plan.taux_par_jour if j.month == 3)
    assert mars == [D("2026-03-05"), D("2026-03-06")] + [date(2026, 3, j) for j in range(9, 14)]


def test_un_cadre_n_a_jamais_de_carence():
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-04"),
                 cadre=True, entree="2022-06-01")
    assert [(a.carence_jours, a.raison_carence) for a in plan.arrets] == [
        (0, RAISON_CADRE), (0, RAISON_CADRE),
    ]
    assert len(plan.taux_par_jour) == 8


def test_cadre_accident_du_travail_a_six_mois_la_tranche_de_deux_ans():
    plan = _plan(_arret("2026-03-02", "2026-07-31", "accident_travail"), cadre=True, entree="2025-09-01")
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-03-02"), D("2026-04-30"), 60)
    assert _bornes(_jours_a(plan, 0.5)) == (D("2026-05-01"), D("2026-06-29"), 60)
    assert plan.arrets[0].limite_atteinte == D("2026-06-29")


def test_cadre_accident_de_trajet_a_six_mois_la_premiere_tranche():
    plan = _plan(_arret("2026-03-02", "2026-07-31", "accident_trajet"), cadre=True, entree="2025-09-01")
    assert len(_jours_a(plan, 1.0)) == 45 and len(_jours_a(plan, 0.5)) == 45


def test_onze_mois_rien_en_maladie_les_paliers_en_accident_du_travail():
    maladie = _plan(_arret("2026-05-05", "2026-05-13"), entree="2025-05-28")
    assert maladie.taux_par_jour == {}
    assert maladie.arrets[0].tranche is None and maladie.arrets[0].mois_anciennete == 11
    at = _plan(_arret("2026-05-05", "2026-09-30", "accident_travail"), entree="2025-05-28")
    assert len(_jours_a(at, 1.0)) == 45 and len(_jours_a(at, 0.75)) == 60


def test_la_limite_annuelle_cumule_les_arrets():
    """Moins de 5 ans : 80 jours au premier arrêt, il en reste 25 pour le second, à 100 %."""
    plan = _plan(_arret("2026-01-05", "2026-03-25"), _arret("2026-06-01", "2026-07-31"),
                 entree="2023-01-01")
    premier = [j for j in plan.taux_par_jour if j < D("2026-04-01")]
    assert len(premier) == 80
    second = sorted(j for j in plan.taux_par_jour if j >= D("2026-06-01"))
    assert _bornes(second) == (D("2026-06-04"), D("2026-06-28"), 25)
    assert {plan.taux_par_jour[j] for j in second} == {1.0}
    assert plan.arrets[1].limite_atteinte == D("2026-06-28")


def test_un_arret_a_cheval_sur_deux_annees_garde_la_limite_de_l_arret():
    plan = _plan(_arret("2026-11-02", "2027-04-30"), entree="2015-01-01")
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-11-02"), D("2026-12-31"), 60)
    assert _bornes(_jours_a(plan, 0.75)) == (D("2027-01-01"), D("2027-03-16"), 75)
    assert plan.arrets[0].limite_atteinte == D("2027-03-16")


def test_cinq_ans_atteints_pendant_l_arret_ne_changent_pas_sa_tranche():
    plan = _plan(_arret("2026-05-04", "2026-09-30"), entree="2021-06-15")
    assert plan.arrets[0].mois_anciennete == 58
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-05-04"), D("2026-06-17"), 45)
    assert _bornes(_jours_a(plan, 0.75)) == (D("2026-06-18"), D("2026-08-16"), 60)


def test_les_conges_de_parentalite_ne_sont_pas_rejoues():
    plan = _plan(_arret("2026-02-02", "2026-03-31", "maternite"), _arret("2026-05-04", "2026-05-08"))
    assert len(plan.arrets) == 1
    assert plan.arrets[0].raison_carence == RAISON_PREMIER_ARRET


def test_l_arret_calcule_s_ajoute_aux_arrets_connus_s_il_n_y_est_pas():
    connus = [{"debut": "2026-02-02", "fin": "2026-02-06", "type": "maladie"}]
    assert len(arrets_pour_le_plan(connus, D("2026-03-02"), D("2026-03-06"), "maladie_simple")) == 2
    assert len(arrets_pour_le_plan(connus, D("2026-02-03"), D("2026-02-05"), "maladie_simple")) == 1
    assert arrets_pour_le_plan(None, D("2026-03-02"), D("2026-03-06"), "ald") == [
        ArretDuPlan(D("2026-03-02"), D("2026-03-06"), "ald"),
    ]


def test_arret_du_jour():
    plan = _plan(_arret("2026-02-02", "2026-02-06"), _arret("2026-03-02", "2026-03-13"))
    assert plan.arret_du_jour(D("2026-03-05")).debut == D("2026-03-02")
    assert plan.arret_du_jour(D("2026-02-20")) is None
