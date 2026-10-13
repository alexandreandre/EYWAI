"""Le mois d'entrée acquiert au prorata des jours, comme Quadra.

Quadra proratise le mois d'entrée aux jours calendaires sur 30 : entrée le
14/09 → 2,08 × 17/30 = 1,18 ; le 28/09 → 0,21 ; le 04/05 → 1,94. Martine
comptait le mois entier (2,08), soit + 0,90 j et + 1,87 j sur les deux entrées
réelles de septembre 2026 (décision du 12/10/2026).

Une reprise de soldes datée après l'entrée a déjà calé le compteur sur l'ancien
logiciel : l'acquis d'avant la reprise ne change pas, sinon le solde repris
bougerait.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import (
    calculate_acquired_cp,
    compute_cp_period_balances,
)

pytestmark = pytest.mark.unit

OUVRES = LeavePolicySettings(cp_acquisition_days_per_month=25 / 12, cp_counting_unit="ouvre")


def test_entree_le_14_septembre_acquiert_17_trentiemes():
    assert calculate_acquired_cp(
        date(2026, 9, 14), date(2026, 9, 30), policy=OUVRES, prorata_mois_d_entree=True
    ) == 1.18


def test_entree_le_28_septembre_acquiert_3_trentiemes():
    assert calculate_acquired_cp(
        date(2026, 9, 28), date(2026, 9, 30), policy=OUVRES, prorata_mois_d_entree=True
    ) == 0.2


def test_le_mois_suivant_compte_entier():
    # 17/30 de septembre puis octobre entier : 1,5667 × 25/12 = 3,26.
    assert calculate_acquired_cp(
        date(2026, 9, 14), date(2026, 10, 31), policy=OUVRES, prorata_mois_d_entree=True
    ) == 3.26


def test_une_entree_le_1er_compte_le_mois_entier():
    assert calculate_acquired_cp(
        date(2026, 9, 1), date(2026, 9, 30), policy=OUVRES, prorata_mois_d_entree=True
    ) == 2.08


def test_entree_et_sortie_le_meme_mois_un_seul_prorata():
    # Du lundi 14 au vendredi 25/09 : 10 jours ouvrés sur 20, comme avant.
    assert calculate_acquired_cp(
        date(2026, 9, 14),
        date(2026, 9, 25),
        policy=OUVRES,
        date_de_sortie=date(2026, 9, 25),
        prorata_mois_d_entree=True,
    ) == 1.04


def test_les_soldes_du_bulletin_portent_le_prorata_d_entree():
    soldes = compute_cp_period_balances(date(2026, 9, 14), [], date(2026, 9, 30), policy=OUVRES)
    assert soldes["periode_courante"]["acquis"] == 1.18
    assert soldes["periode_courante"]["solde"] == 1.18


def test_une_reprise_datee_apres_l_entree_garde_son_solde():
    # Entrée le 24/08, reprise au 31/08 qui a recalé le compteur sur Quadra.
    reprise = EmployeeLeaveAdjustment(
        cp_n_opening_balance=-1.53, cp_opening_reference_date=date(2026, 8, 31)
    )
    soldes = compute_cp_period_balances(
        date(2026, 8, 24), [], date(2026, 9, 30), policy=OUVRES, adjustment=reprise
    )
    assert soldes["periode_courante"]["acquis"] == 4.16
    assert soldes["periode_courante"]["solde"] == 2.63


def test_une_entree_apres_la_reprise_est_proratisee():
    reprise = EmployeeLeaveAdjustment(cp_opening_reference_date=date(2026, 8, 31))
    soldes = compute_cp_period_balances(
        date(2026, 9, 14), [], date(2026, 9, 30), policy=OUVRES, adjustment=reprise
    )
    assert soldes["periode_courante"]["acquis"] == 1.18
