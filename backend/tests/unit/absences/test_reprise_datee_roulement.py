"""Le roulement d'une reprise de congés regarde la date de la reprise.

Une reprise calibre les deux périodes en cours à sa date de référence. Tant que
le bulletin est dans la même période, ses écarts s'appliquent tels quels ; à la
période suivante, le solde N repris devient le stock N-1 (roulement) ; deux
périodes plus tard, la reprise ne dit plus rien.

Le roulement se déclenchait sur « écart N non nul et bulletin après le 1er
juin », sans regarder la date de la reprise : une reprise datée d'août, donc
déjà dans la nouvelle période, était rejouée comme si elle venait de mai
(Fuckar, Colorplast : N à 3,24 au lieu de −0,43). Les reprises sans date
gardent l'ancien comportement.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.absences.domain.leave_policy import (
    EmployeeLeaveAdjustment,
    LeavePolicySettings,
)
from app.modules.absences.domain.rules import compute_cp_period_balances

pytestmark = pytest.mark.unit

POLITIQUE = LeavePolicySettings(cp_reference_period_start_month=6, cp_carryover_enabled=True)
ENTREE = date(2020, 1, 1)
#: 12 jours pris en août 2026, 5 en août 2027.
AOUT_2026 = [f"2026-08-{d:02d}" for d in (3, 4, 5, 6, 7, 10, 11, 12, 13, 14, 17, 18)]
AOUT_2027 = [f"2027-08-{d:02d}" for d in (2, 3, 4, 5, 6)]
DEMANDES = [
    {"type": "conge_paye", "status": "validated", "selected_days": AOUT_2026, "jours_payes": 12.0},
    {"type": "conge_paye", "status": "validated", "selected_days": AOUT_2027, "jours_payes": 5.0},
]
#: Reprise au 30/06/2026 : 15 jours de plus que le théorique en N-1, N juste.
REPRISE = EmployeeLeaveAdjustment(
    cp_n1_opening_balance=15.0,
    cp_n_opening_balance=0.0,
    cp_opening_reference_date=date(2026, 6, 30),
)


def _soldes(ref: date, ajustement: EmployeeLeaveAdjustment) -> dict:
    return compute_cp_period_balances(ENTREE, DEMANDES, ref, policy=POLITIQUE, adjustment=ajustement)


def test_dans_la_periode_de_la_reprise_les_ecarts_s_appliquent_tels_quels():
    soldes = _soldes(date(2027, 3, 31), REPRISE)

    # 30 acquis en 2025-26 + 15 repris − 12 pris en août 2026 (sur le stock N-1)
    assert soldes["n1_remaining"] == 33.0


def test_a_la_periode_suivante_le_solde_n_repris_devient_le_stock_n_1():
    soldes = _soldes(date(2027, 6, 30), REPRISE)

    # Le N de 2026-27 se fermait à 30 (les 12 jours d'août sont sortis du N-1) :
    # c'est le nouveau N-1, sans les 15 jours du stock 2025-26, épuisé ou perdu.
    assert soldes["n1_remaining"] == 30.0
    # Juin acquis : 2,5 j arrondis à l'entier supérieur en jours ouvrables.
    assert soldes["n_remaining"] == 3.0


def test_deux_periodes_plus_tard_la_reprise_ne_dit_plus_rien():
    soldes = _soldes(date(2028, 6, 30), REPRISE)

    # 30 acquis en 2027-28 − 5 pris en août 2027, sans trace de la reprise
    assert soldes["n1_remaining"] == 25.0


def test_une_reprise_sans_date_garde_l_ancien_comportement():
    sans_date = EmployeeLeaveAdjustment(cp_n1_opening_balance=15.0, cp_n_opening_balance=0.0)

    soldes = _soldes(date(2027, 6, 30), sans_date)

    # Écart N nul : jamais roulé, l'écart N-1 s'applique à chaque période.
    assert soldes["n1_remaining"] == 33.0


def test_une_reprise_datee_apres_le_1er_juin_n_est_pas_rejouee_comme_venant_de_mai():
    """Fuckar : reprise au 31/08 avec un écart N ; le bulletin de septembre est
    dans la même période, l'écart N s'applique tel quel."""
    reprise_aout = EmployeeLeaveAdjustment(
        cp_n1_opening_balance=-2.0,
        cp_n_opening_balance=-6.67,
        cp_opening_reference_date=date(2026, 8, 31),
    )

    soldes = compute_cp_period_balances(
        date(2026, 4, 7), [], date(2026, 9, 30), policy=POLITIQUE, adjustment=reprise_aout
    )

    # N : 4 mois × 2,5 = 10 acquis, moins l'écart 6,67
    assert soldes["n_remaining"] == pytest.approx(3.33, abs=0.01)
