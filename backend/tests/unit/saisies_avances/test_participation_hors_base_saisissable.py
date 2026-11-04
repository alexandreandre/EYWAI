"""La participation et l'intéressement n'entrent pas dans la base saisissable.

service-public, F115 « Saisie sur salaire » (vérifié le 01/04/2026, ouvert le
04/11/2026) : « certaines sommes ne font pas partie du revenu saisissable : […]
Primes de participation et d'intéressement ». Audit du 03/11/2026 (lot D,
verdicts 3 et 4b) : en mai, mois de la participation, des saisies et des prêts
dépassaient la quotité dès qu'on retire la participation de la base.

Le barème 2026 (R3252-2, R3252-3 ; 373,33 / 727,50 / 1 083,33 / 1 435,83 /
1 789,17 / 2 150,83 € par mois, 145 € par personne à charge, 651,69 € laissés)
est déjà appliqué : `test_quotite_saisissable_legale.py`. Les prêts y sont
plafonnés depuis le 31/10/2026 (Cass. soc. 15/01/2014).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.saisies_avances.domain import rules

pytestmark = pytest.mark.unit

PARTICIPATION = {
    "libelle": "Participation 2025 — numéraire",
    "brut": 2120.19,
    "csg_deductible": 144.17,
    "csg_non_deductible": 61.49,
    "csg_total": 205.66,
    "acompte": 0.0,
    "part_pee": 0.0,
}


def _bulletin(net, participations=(), primes=()):
    return {
        "net_a_payer": net,
        "synthese_net": {},
        "participations": list(participations),
        "primes_non_soumises": list(primes),
    }


def test_la_participation_versee_sort_de_la_base():
    # 1 500 € de salaire net + 1 914,53 € de participation nette (2 120,19 − 205,66).
    bulletin = _bulletin(3414.53, [PARTICIPATION])
    assert rules.base_saisissable(bulletin) == Decimal("1500.00")
    _net, elements = rules.composition_base_saisissable(bulletin)
    assert ("participation et intéressement", Decimal("-1914.53")) in elements


def test_la_part_placee_sur_le_plan_d_epargne_ne_compte_pas_deux_fois():
    """Seule la part versée est au net à payer : seule elle en sort."""
    placee = {**PARTICIPATION, "part_pee": 2120.19}
    assert rules.base_saisissable(_bulletin(1500.0, [placee])) == Decimal("1500.00")


def test_l_acompte_deja_verse_sort_avec_la_participation():
    """L'acompte retenu ce mois-ci est de la participation, pas du salaire."""
    acompte = {"libelle": "Acompte sur participation 2025 (déjà versé)", "montant": -500.0}
    bulletin = _bulletin(3414.53 - 500.0, [PARTICIPATION], [acompte])
    assert rules.base_saisissable(bulletin) == Decimal("1500.00")


def test_un_mois_sans_participation_ne_change_pas():
    assert rules.base_saisissable(_bulletin(1500.0)) == Decimal("1500.00")
