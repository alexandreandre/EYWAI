"""Un solde de congés repris s'affiche tel qu'il a été importé.

L'affichage ajoute les congés d'ancienneté et le fractionnement, que le solde de
l'ancien logiciel comprend déjà : l'ouverture est recalée sur l'affiché.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.modules.absences.application import leave_settings_commands as cmd

pytestmark = pytest.mark.unit


def test_l_ouverture_est_recalee_sur_le_solde_affiche():
    ecrits = []
    theorique = {"n1_remaining": 20.0, "n_remaining": 2.08}
    affiche = {"conges_payes_periode_precedente": {"solde": 38.5}, "conges_payes": {"solde": 7.16}}
    with (
        patch("app.modules.absences.infrastructure.queries.get_employee_hire_date", return_value="1996-10-01"),
        patch.object(cmd, "get_leave_policy", return_value=None),
        patch.object(cmd, "absence_repository"),
        patch("app.modules.absences.domain.rules.compute_cp_period_balances", return_value=theorique),
        patch("app.modules.absences.domain.rules.compute_rtt_balance", return_value={"solde": 0.0}),
        patch.object(cmd, "bulletin_reference_date", return_value=date(2026, 7, 31)),
        patch.object(cmd, "upsert_employee_adjustment", side_effect=lambda c, e, y, p: ecrits.append(dict(p))),
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip", return_value=affiche),
    ):
        cmd.apply_cp_solde_import("co", "e1", 2026, cp_n1_solde=35.5, cp_n_solde=4.16, month=7)

    premier, recale = ecrits
    assert premier["cp_n1_opening_balance"] == 15.5 and premier["cp_n_opening_balance"] == 2.08
    # L'affiché dépassait de 3 jours (ancienneté) : l'ouverture en retire 3.
    assert recale["cp_n1_opening_balance"] == 12.5
    assert recale["cp_n_opening_balance"] == -0.92


def test_rien_n_est_reecrit_quand_l_affiche_est_deja_juste():
    ecrits = []
    with (
        patch("app.modules.absences.infrastructure.queries.get_employee_hire_date", return_value="2019-10-01"),
        patch.object(cmd, "get_leave_policy", return_value=None),
        patch.object(cmd, "absence_repository"),
        patch("app.modules.absences.domain.rules.compute_cp_period_balances",
              return_value={"n1_remaining": 10.0, "n_remaining": 2.08}),
        patch("app.modules.absences.domain.rules.compute_rtt_balance", return_value={"solde": 0.0}),
        patch.object(cmd, "bulletin_reference_date", return_value=date(2026, 7, 31)),
        patch.object(cmd, "upsert_employee_adjustment", side_effect=lambda c, e, y, p: ecrits.append(p)),
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip",
              return_value={"conges_payes_periode_precedente": {"solde": 12.0}, "conges_payes": {"solde": 4.16}}),
    ):
        cmd.apply_cp_solde_import("co", "e1", 2026, cp_n1_solde=12.0, cp_n_solde=4.16, month=7)
    assert len(ecrits) == 1


def test_un_solde_repris_negatif_n_est_ni_rabote_ni_corrige_deux_fois():
    """Quadra : −0,43 j (congés pris par anticipation). Notre décompte théorique
    est à −0,76 : l'ouverture vaut +0,33. L'affichage plancher à zéro montre 0,
    ce qui ne dit rien du solde réel : pas de second recalage (29/09/2026,
    reprise d'août, l'ouverture était tombée à −0,86)."""
    ecrits = []
    with (
        patch("app.modules.absences.infrastructure.queries.get_employee_hire_date", return_value="2026-04-07"),
        patch.object(cmd, "get_leave_policy", return_value=None),
        patch.object(cmd, "absence_repository"),
        patch("app.modules.absences.domain.rules.compute_cp_period_balances",
              return_value={"n1_remaining": 0.0, "n_remaining": 0.0, "n_remaining_brut": -0.76}),
        patch("app.modules.absences.domain.rules.compute_rtt_balance", return_value={"solde": 0.0}),
        patch.object(cmd, "bulletin_reference_date", return_value=date(2026, 8, 31)),
        patch.object(cmd, "upsert_employee_adjustment", side_effect=lambda c, e, y, p: ecrits.append(dict(p))),
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip",
              return_value={"conges_payes_periode_precedente": {"solde": 0.0}, "conges_payes": {"solde": 0.0}}),
    ):
        cmd.apply_cp_solde_import("co", "e1", 2026, cp_n1_solde=0.0, cp_n_solde=-0.43, month=8)
    assert len(ecrits) == 1
    assert ecrits[0]["cp_n1_opening_balance"] == 0.0
    assert ecrits[0]["cp_n_opening_balance"] == 0.33


def _importer(theorique, affiche, cible_n):
    ecrits = []
    with (
        patch("app.modules.absences.infrastructure.queries.get_employee_hire_date", return_value="2026-01-05"),
        patch.object(cmd, "get_leave_policy", return_value=None),
        patch.object(cmd, "absence_repository"),
        patch("app.modules.absences.domain.rules.compute_cp_period_balances", return_value=theorique),
        patch("app.modules.absences.domain.rules.compute_rtt_balance", return_value={"solde": 0.0}),
        patch.object(cmd, "bulletin_reference_date", return_value=date(2026, 8, 31)),
        patch.object(cmd, "upsert_employee_adjustment", side_effect=lambda c, e, y, p: ecrits.append(dict(p))),
        patch("app.modules.absences.application.queries.get_absence_balances_for_payslip", return_value=affiche),
    ):
        cmd.apply_cp_solde_import("co", "e1", 2026, cp_n1_solde=0.0, cp_n_solde=cible_n, month=8)
    return ecrits


def test_un_solde_repris_negatif_mais_affiche_positif_est_recale():
    """−0,76 chez Quadra ; l'affichage ajoute un jour (ancienneté) et montre 0,24 :
    il se lit, l'ouverture en retire 1."""
    ecrits = _importer({"n1_remaining": 0.0, "n_remaining": 0.0, "n_remaining_brut": -1.2},
                       {"conges_payes_periode_precedente": {"solde": 0.0}, "conges_payes": {"solde": 0.24}},
                       -0.76)
    assert [e["cp_n_opening_balance"] for e in ecrits] == [0.44, -0.56]


def test_sans_compteur_a_la_date_de_reprise_l_ouverture_reste():
    """Fiche arrêtée avant la reprise : aucun compteur à comparer, pas d'erreur."""
    ecrits = _importer({"n1_remaining": 0.0, "n_remaining": 0.0, "n_remaining_brut": 0.0}, None, 0.07)
    assert len(ecrits) == 1 and ecrits[0]["cp_n_opening_balance"] == 0.07
