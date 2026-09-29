"""Le mois de sortie n'acquiert que la part travaillée.

Un mois de travail effectif vaut quatre semaines (C. trav. L3141-3 et L3141-4) :
24 jours ouvrables, ou 20 jours ouvrés quand la société décompte en ouvrés. Une
fin de CDD le 15/09 comptait tout septembre (2,09 j au lieu de 1,15 j) et
gonflait l'indemnité de congés du solde de tout compte (Colorplast, 29/09/2026).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.domain.leave_policy import LeavePolicySettings
from app.modules.absences.domain.rules import (
    _fraction_du_mois_de_sortie,
    calculate_acquired_cp,
    compute_cp_period_balances,
)

pytestmark = pytest.mark.unit

OUVRES = LeavePolicySettings(cp_acquisition_days_per_month=25 / 12, cp_counting_unit="ouvre")


def test_la_part_du_mois_de_sortie_suit_l_unite_de_decompte():
    # Du mardi 01/09 au mardi 15/09/2026 : 11 jours ouvrés, 13 jours ouvrables.
    assert _fraction_du_mois_de_sortie(date(2026, 4, 7), date(2026, 9, 15), OUVRES) == pytest.approx(11 / 20)
    assert _fraction_du_mois_de_sortie(date(2026, 4, 7), date(2026, 9, 15), LeavePolicySettings()) == pytest.approx(13 / 24)


def test_un_mois_de_sortie_complet_compte_pour_un_mois():
    assert _fraction_du_mois_de_sortie(date(2026, 4, 7), date(2026, 9, 30), OUVRES) == 1.0
    # Quatre semaines de travail suffisent : du 01/09 au 28/09, 20 jours ouvrés.
    assert _fraction_du_mois_de_sortie(date(2026, 4, 7), date(2026, 9, 28), OUVRES) == 1.0


def test_l_acquis_au_jour_de_sortie_est_proratise():
    embauche, sortie = date(2026, 4, 7), date(2026, 9, 15)
    # Juin, juillet, août entiers puis 11/20 de septembre : 3,55 × 25/12 = 7,39.
    assert calculate_acquired_cp(embauche, sortie, policy=OUVRES, date_de_sortie=sortie) == 7.39
    # Sans date de sortie (solde consulté en cours de mois), rien ne change.
    assert calculate_acquired_cp(embauche, sortie, policy=OUVRES) == 8.33


def test_les_soldes_du_bulletin_de_sortie_portent_le_prorata():
    embauche, sortie = date(2026, 4, 7), date(2026, 9, 15)
    soldes = compute_cp_period_balances(embauche, [], sortie, policy=OUVRES, date_de_sortie=sortie)
    assert soldes["periode_courante"]["acquis"] == 7.39
