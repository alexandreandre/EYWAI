"""Plan conventionnel des jours d'arrêt, barème de la métallurgie (pur).

Pas de carence, trois mois en accident du travail, ancienneté lue chaque jour,
paliers consommés sur l'année civile (art. 91.1.1 à 91.1.3). Conception du
03/11/2026. Initiales seulement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.domain.baremes_maintien import METALLURGIE
from app.modules.payroll.engine.paliers_convention import (
    ArretDuPlan,
    plan_conventionnel,
)

pytestmark = pytest.mark.unit

D = date.fromisoformat


def _arret(debut, fin, type_arret="maladie_simple"):
    return ArretDuPlan(D(debut), D(fin), type_arret)


def _plan(*arrets, cadre=False, entree="2015-01-01"):
    return plan_conventionnel(list(arrets), bareme=METALLURGIE, est_cadre=cadre, date_anciennete=D(entree))


def _jours_a(plan, taux):
    return sorted(j for j, t in plan.taux_par_jour.items() if t == taux)


def _bornes(jours):
    return (jours[0], jours[-1], len(jours)) if jours else None


def _indemnises(plan, index):
    return [j for j in plan.arrets[index].jours if j in plan.taux_par_jour]


def _par_an(plan):
    compte: dict[int, int] = {}
    for j in plan.taux_par_jour:
        compte[j.year] = compte.get(j.year, 0) + 1
    return compte


def test_pas_de_carence():
    """Non-cadre, 3 ans, 100 % dès le premier jour, sans carence."""
    plan = _plan(_arret("2026-03-02", "2026-03-20"), entree="2023-01-01")
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-03-02"), D("2026-03-20"), 19)
    (arret,) = plan.arrets
    assert arret.carence_jours == 0
    assert arret.jours_de_carence == ()


def test_accident_du_travail_indemnise_des_trois_mois_acquis_pendant_l_arret():
    """Entré le 10/01, accident du travail du 02/04 : droit au 10/04 (3 mois), crédit entier."""
    plan = _plan(_arret("2026-04-02", "2026-04-20", "accident_travail"), entree="2026-01-10")
    jours = _jours_a(plan, 1.0)
    assert jours[0] == D("2026-04-10")
    assert D("2026-04-05") not in plan.taux_par_jour
    assert _bornes(jours) == (D("2026-04-10"), D("2026-04-20"), 11)


def test_un_cadre_passe_a_cinquante_pour_cent_apres_quatre_vingt_dix_jours():
    """Cadre, 2 ans : 90 j à 100 %, puis 90 j à 50 %, limite 180 j."""
    plan = _plan(_arret("2026-01-01", "2026-06-30"), cadre=True, entree="2024-01-01")
    assert _bornes(_jours_a(plan, 1.0)) == (D("2026-01-01"), D("2026-03-31"), 90)
    assert _bornes(_jours_a(plan, 0.5)) == (D("2026-04-01"), D("2026-06-29"), 90)
    assert D("2026-06-30") not in plan.taux_par_jour
    assert plan.arrets[0].limite_atteinte == D("2026-06-29")


def test_a_cheval_sans_incapacite_anterieure_l_annee_n_allonge_pas():
    """Cas 1 de l'art. 91.1.3 : 120 j au total, le passage à 2027 n'allonge rien."""
    plan = _plan(_arret("2026-11-01", "2027-03-31"), entree="2018-01-01")
    assert _par_an(plan) == {2026: 61, 2027: 59}
    assert len(plan.taux_par_jour) == 120
    assert D("2027-03-01") not in plan.taux_par_jour


def test_a_cheval_apres_une_incapacite_anterieure_credit_reevalue_au_1er_janvier():
    """Cas 2 : un premier arrêt en 2026, puis un arrêt à cheval réévalué à 120 j au 01/01/2027."""
    plan = _plan(
        _arret("2026-02-01", "2026-02-20"),
        _arret("2026-12-01", "2027-04-30"),
        entree="2018-01-01",
    )
    assert len(_indemnises(plan, 0)) == 20
    jours2 = _indemnises(plan, 1)
    assert len(jours2) == 120
    assert sum(1 for j in jours2 if j.year == 2026) == 31
    assert sum(1 for j in jours2 if j.year == 2027) == 89


def test_nouvel_arret_posterieur_deduit_ce_qui_a_ete_indemnise_depuis_le_1er_janvier():
    """Cas 3 : après un arrêt qui a pris 51 j en 2027, le suivant n'a plus que 120 − 51 = 69 j."""
    plan = _plan(
        _arret("2027-01-10", "2027-03-01"),
        _arret("2027-05-01", "2027-12-31"),
        entree="2018-01-01",
    )
    assert len(_indemnises(plan, 0)) == 51
    assert len(_indemnises(plan, 1)) == 69
