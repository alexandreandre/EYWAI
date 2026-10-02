"""Absence sur tout le mois : la retenue égale le salaire mensualisé, jamais plus.

Un salarié à 39 h (base à 35 h + heures structurelles) absent tous les jours
ouvrés d'un mois de 22 jours : la retenue jour par jour donne 22 × 7,8 h =
171,6 h, plus que les 169 h du salaire mensualisé. Quadra retient exactement
le salaire (« Absence maladie 010726-310726 » = salaire de base, juillet 2026
à 22 jours ouvrés) : le bulletin ne doit pas retenir plus que ce qu'il paie.
"""

from datetime import date, timedelta

import pytest

from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _ctx_39h():
    ctx = build_test_contexte(salaire_base=1952.60, duree_hebdo=39.0)
    ctx.contrat["specificites_paie"] = {"salaire_hors_hs_structurelles": True}
    ctx.baremes.setdefault("heures_supp", {}).setdefault(
        "regles_calcul_communes", {}
    ).setdefault("taux_majoration_par_defaut", {})["heures_supplementaires"] = [
        {"taux": 0.25},
        {"taux": 0.50},
    ]
    return ctx


def _arret_tous_les_jours_ouvres(annee: int, mois: int) -> list[dict]:
    jour = date(annee, mois, 1)
    cal = []
    while jour.month == mois:
        if jour.weekday() < 5:
            cal.append(
                {
                    "date_complete": jour.isoformat(),
                    "type": "arret_maladie",
                    "heures": 7.8,
                    "arret_type": "maladie_simple",
                }
            )
        jour += timedelta(days=1)
    return cal


def _solde_salaire(result: dict) -> float:
    """Brut du salaire après retenues (le contexte de test n'a pas de prime)."""
    return round(float(result["salaire_brut_total"]), 2)


def test_un_mois_de_22_jours_ouvres_absent_ne_retient_pas_plus_que_le_salaire():
    cal = _arret_tous_les_jours_ouvres(2026, 9)
    assert len(cal) == 22
    result = calculer_salaire_brut(
        _ctx_39h(), cal, date(2026, 9, 1), date(2026, 9, 30), nb_jours_travail_planifies=0
    )
    assert _solde_salaire(result) == 0.0


def test_un_mois_de_21_jours_ouvres_absent_retient_tout_le_salaire():
    cal = _arret_tous_les_jours_ouvres(2026, 8)
    assert len(cal) == 21
    result = calculer_salaire_brut(
        _ctx_39h(), cal, date(2026, 8, 1), date(2026, 8, 31), nb_jours_travail_planifies=0
    )
    assert _solde_salaire(result) == 0.0


def test_un_mois_avec_un_jour_travaille_garde_la_retenue_jour_par_jour():
    cal = _arret_tous_les_jours_ouvres(2026, 9)
    retenue_22_jours = calculer_salaire_brut(
        _ctx_39h(), cal, date(2026, 9, 1), date(2026, 9, 30), nb_jours_travail_planifies=1
    )
    assert _solde_salaire(retenue_22_jours) < 0.0
