"""Préavis d'un départ ou d'une mise à la retraite : celui du licenciement.

Code du travail (Légifrance, ouverts le 11/10/2026) :
- art. L1237-6 (en vigueur depuis le 01/05/2008) : « L'employeur qui décide une
  mise à la retraite respecte un préavis dont la durée est déterminée
  conformément à l'article L. 1234-1. » ;
- art. L1237-10 (en vigueur depuis le 01/05/2008) : « Le salarié demandant son
  départ à la retraite respecte un préavis dont la durée est déterminée
  conformément à l'article L. 1234-1. » ;
- art. L1234-1 (en vigueur depuis le 01/05/2008) : un mois de six mois à moins
  de deux ans d'ancienneté, deux mois au-delà ; sous six mois, la loi, la
  convention ou les usages.

Martine disait « Préavis non applicable » pour tout départ à la retraite, et
l'écran cachait la durée et l'exécution du préavis.
"""

from datetime import date

import pytest

from app.modules.employee_exits.domain.notice_period import compute_notice_period

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "entree,jours",
    [(date(2010, 1, 1), 60), (date(2025, 1, 1), 30), (date(2026, 4, 1), 0)],
)
def test_le_depart_a_la_retraite_propose_le_preavis_de_l1234_1(entree, jours):
    result = compute_notice_period(
        exit_type="depart_retraite",
        hire_date=entree,
        reference_date=date(2026, 7, 1),
        statut="Employé",
    )
    assert result.applicable is True
    assert result.source == "legal"
    assert result.days == jours
    assert "L1237-6" in result.detail and "L1237-10" in result.detail and "L1234-1" in result.detail


def test_une_regle_de_convention_pour_le_licenciement_vaut_pour_la_retraite():
    result = compute_notice_period(
        exit_type="depart_retraite",
        hire_date=date(2010, 1, 1),
        reference_date=date(2026, 7, 1),
        statut="Cadre",
        collective_agreement_name="Plasturgie",
        collective_agreement_idcc="0292",
        cc_rules={"preavis": {"licenciement": {"cadre": [{"anciennete_mois_min": 0, "mois": 3}]}}},
    )
    assert result.days == 90
    assert result.source == "convention"


def test_la_rupture_conventionnelle_reste_sans_preavis_et_ne_parle_plus_de_retraite():
    result = compute_notice_period(
        exit_type="rupture_conventionnelle",
        hire_date=date(2010, 1, 1),
        reference_date=date(2026, 7, 1),
        statut="Employé",
    )
    assert result.applicable is False
    assert "retraite" not in result.detail
