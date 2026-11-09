"""Métallurgie, art. 91.1.3 : année civile, et pas de crédit neuf sans reprise.

Cas rejoués sur des dates inspirées de l'audit du 02/11/2026 (Cartol), sans
donnée de salarié. Texte : Légifrance, relu le 03/11/2026.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.domain.baremes_maintien import METALLURGIE, PLASTURGIE
from app.modules.payroll.engine.paliers_convention import (
    ArretDuPlan,
    plan_conventionnel,
)

pytestmark = pytest.mark.unit

ANCIENNETE = date(2019, 1, 1)  # de 5 à 10 ans sur toute la période : 120 jours


def _plan(arrets, bareme=METALLURGIE):
    return plan_conventionnel(
        arrets, bareme=bareme, est_cadre=False, date_anciennete=ANCIENNETE
    )


def _jours_de(plan, annee):
    return [j for j in plan.taux_par_jour if j.year == annee]


def test_at_puis_maladie_sans_reprise_pas_de_credit_neuf():
    """AT à cheval sur deux ans, crédit épuisé, maladie le lendemain : rien."""
    plan = _plan(
        [
            ArretDuPlan(date(2025, 3, 7), date(2026, 3, 31), "accident_travail"),
            ArretDuPlan(date(2026, 4, 1), date(2026, 9, 30), "maladie_simple"),
        ]
    )
    assert len(_jours_de(plan, 2025)) == 120
    assert _jours_de(plan, 2026) == []


def test_at_puis_maladie_sans_reprise_consomme_le_reste_du_credit():
    """AT de 30 jours, maladie le lendemain : 90 jours restent, pas 120."""
    plan = _plan(
        [
            ArretDuPlan(date(2026, 1, 1), date(2026, 1, 30), "accident_travail"),
            ArretDuPlan(date(2026, 1, 31), date(2026, 9, 30), "maladie_simple"),
        ]
    )
    assert len(_jours_de(plan, 2026)) == 120


def test_avec_reprise_effective_un_nouvel_arret_ouvre_le_credit():
    """Deux jours travaillés entre les deux : le crédit de l'année s'applique."""
    plan = _plan(
        [
            ArretDuPlan(date(2025, 3, 7), date(2026, 3, 31), "accident_travail"),
            ArretDuPlan(date(2026, 4, 3), date(2026, 9, 30), "maladie_simple"),
        ]
    )
    assert len(_jours_de(plan, 2026)) == 120


def test_le_credit_se_compte_sur_l_annee_civile():
    """Absences séparées par une reprise : 120 jours au plus dans l'année."""
    plan = _plan(
        [
            ArretDuPlan(date(2026, 2, 1), date(2026, 4, 30), "maladie_simple"),
            ArretDuPlan(date(2026, 6, 1), date(2026, 9, 30), "maladie_simple"),
        ]
    )
    assert len(_jours_de(plan, 2026)) == 120


def test_l_annee_suivante_rouvre_le_credit_apres_reprise():
    plan = _plan(
        [
            ArretDuPlan(date(2026, 6, 1), date(2026, 11, 30), "maladie_simple"),
            ArretDuPlan(date(2027, 2, 1), date(2027, 3, 31), "maladie_simple"),
        ]
    )
    assert len(_jours_de(plan, 2027)) == 59


def test_la_plasturgie_ne_change_pas():
    """Colorplast et Comitech : le rang repart à chaque arrêt, comme avant."""
    arrets = [
        ArretDuPlan(date(2026, 1, 5), date(2026, 3, 31), "accident_travail"),
        ArretDuPlan(date(2026, 4, 1), date(2026, 5, 31), "maladie_simple"),
    ]
    plan = plan_conventionnel(
        arrets, bareme=PLASTURGIE, est_cadre=False, date_anciennete=ANCIENNETE
    )
    premier_de_la_maladie = date(2026, 4, 1)
    assert plan.taux_par_jour.get(premier_de_la_maladie) == 1.0
