"""Reprise de soldes : l'ouverture se calcule avec la règle qui la relira.

Le mois d'entrée acquiert au prorata, sauf derrière une reprise datée après
l'entrée, dont le solde ne bouge pas (`rules._prorata_du_mois_d_entree`).
L'acquis théorique de la reprise se calculait avec un ajustement vide, donc au
prorata, puis se relisait derrière la reprise datée, mois d'entrée entier :
entrée le 29/06, reprise au 30/09 à solde 0, ouverture −6,38 relue
8,33 − 6,38 = 1,95 jour au lieu de 0. Le recalage sur l'affiché rattrapait
l'écart, sauf quand l'affiché était vide ce jour-là.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.absences.application import leave_settings_commands as cmd
from app.modules.absences.domain.leave_policy import DEFAULT_LEAVE_POLICY

pytestmark = pytest.mark.unit


def test_l_ouverture_d_une_reprise_datee_apres_l_entree_compte_le_mois_d_entree_entier():
    ecrits = []
    with (
        patch("app.modules.absences.infrastructure.queries.get_employee_hire_date", return_value="2026-06-29"),
        patch.object(cmd, "get_leave_policy", return_value=DEFAULT_LEAVE_POLICY),
        patch.object(cmd.absence_repository, "list_validated_for_employees", return_value=[]),
        patch("app.modules.absences.domain.rules.compute_rtt_balance", return_value={"solde": 0.0}),
        patch.object(cmd, "upsert_employee_adjustment", side_effect=lambda c, e, y, p: ecrits.append(dict(p))),
        patch.object(cmd, "oublier_dates_de_reprise", create=True),
        patch("app.modules.absences.infrastructure.repository.oublier_dates_de_reprise"),
        # Le jour de la reprise, l'affiché était vide : le recalage ne joue pas.
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip", return_value=None),
    ):
        cmd.apply_cp_solde_import("co", "e1", 2026, cp_n1_solde=0.0, cp_n_solde=0.0, month=9)

    # Règle de lecture : juin à septembre entiers, 4 × 2,5 = 10 jours ouvrables
    # (et non 8 au prorata du 29/06) ; solde 0 au 30/09.
    assert ecrits[0]["cp_n_opening_balance"] == -10.0
    assert ecrits[0]["cp_opening_reference_date"] == "2026-09-30"
