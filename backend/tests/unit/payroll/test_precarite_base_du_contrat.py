"""Indemnité de fin de CDD : sa base est toute la rémunération du contrat.

Code du travail, L1243-8 : l'indemnité de fin de contrat « est égale à 10 % de
la rémunération totale brute versée au salarié » (au titre du contrat,
renouvellements compris, puisqu'un renouvellement ne crée pas de contrat).
Audit du 03/11/2026 (lot F, verdicts 2 et 3) : l'ancien logiciel prenait une
base tronquée, ou y mettait un contrat précédent (un CDI de janvier-février dans
la base d'un CDD de juin-septembre).

Martine prend le cumul `brut_total` du mois d'avant. Pour un mois repris de
l'ancien logiciel, c'est le cumul de l'année civile : un contrat précédent de
l'année y reste. Ce qu'il y a laissé (le cumul du dernier mois avant le début
du contrat) sort maintenant de la base ; un cumul reparti de zéro au premier
mois du contrat n'a rien à retirer. Les cumuls, pas les bulletins : les mois
repris suivent le cumul du cabinet, et un ancien brouillon peut ne plus y
correspondre (filet du 04/11 : un brouillon d'avril à 216,58 € pour un cumul de
280,23 €). Un contrat commencé une année d'avant : le bulletin le signale.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import _calculer_prime_precarite_cdd
from app.modules.payroll.engine.reference_remuneration import (
    base_precarite_du_bulletin,
    cumul_avant_le_contrat,
)
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _cumul(annee, mois, brut_total):
    return {"employee_id": "emp-1", "year": annee, "month": mois, "cumuls": {"cumuls": {"brut_total": brut_total}}}


def test_le_cumul_laisse_par_le_contrat_d_avant():
    base = BaseEnMemoire({
        "employee_schedules": [
            _cumul(2026, 1, 818.18), _cumul(2026, 2, 3818.18),  # un CDI de janvier-février
            _cumul(2026, 6, 4090.91),  # premier mois du CDD, cumul de l'année civile
            _cumul(2026, 8, 10090.91),
        ]
    })
    assert cumul_avant_le_contrat("emp-1", date(2026, 6, 29), base) == {
        "debut": "2026-06-29", "brut_total_avant": 3818.18, "brut_total_au_debut": 4090.91,
    }


def test_sans_contrat_d_avant_rien_n_est_laisse():
    base = BaseEnMemoire({"employee_schedules": [_cumul(2026, 4, 280.23)]})
    assert cumul_avant_le_contrat("emp-1", date(2026, 4, 21), base) == {
        "debut": "2026-04-21", "brut_total_avant": 0.0, "brut_total_au_debut": 280.23,
    }


def _cdd_de_septembre(avant_le_contrat, brut_total=10090.91, debut="2026-06-29"):
    ctx = build_test_contexte(
        type_contrat="CDD",
        date_entree=debut,
        date_fin_contrat="2026-09-30",
        cumuls={"brut_total": brut_total},
    )
    if avant_le_contrat is not None:
        ctx.contrat["contrat"]["cumul_avant_le_contrat"] = avant_le_contrat
    return ctx


def test_le_contrat_d_avant_sort_de_la_base():
    """Le cas de l'audit : 9 272,73 € de CDD (6 272,73 + 3 000), 3 818,18 € de CDI
    d'avant dans le cumul de l'année."""
    ctx = _cdd_de_septembre({"debut": "2026-06-29", "brut_total_avant": 3818.18, "brut_total_au_debut": 4090.91})
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 927.27


def test_un_cumul_reparti_de_zero_au_debut_du_contrat_n_a_rien_a_retirer():
    ctx = _cdd_de_septembre(
        {"debut": "2026-06-29", "brut_total_avant": 3818.18, "brut_total_au_debut": 272.73},
        brut_total=6272.73,
    )
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 927.27


def test_sans_contrat_d_avant_la_base_ne_change_pas():
    ctx = _cdd_de_septembre({"debut": "2026-06-29", "brut_total_avant": 0.0, "brut_total_au_debut": 272.73},
                            brut_total=6272.73)
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 927.27
    assert not [a for a in ctx.alertes_baremes if str(a.get("code", "")).startswith("precarite")]


def test_sans_lecture_des_cumuls_le_cumul_d_avant():
    ctx = _cdd_de_septembre(None)
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 1309.09


def test_un_contrat_commence_l_annee_d_avant_est_signale():
    ctx = _cdd_de_septembre({"debut": "2025-11-03", "brut_total_avant": 0.0, "brut_total_au_debut": 1800.0},
                            debut="2025-11-03")
    _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    alertes = [a for a in ctx.alertes_baremes if a.get("code") == "precarite_base_annee_precedente"]
    assert alertes and "2025" in alertes[0]["message"]


def test_le_bulletin_lit_le_cumul_seulement_au_dernier_mois_d_un_cdd():
    base = BaseEnMemoire({"employee_schedules": [_cumul(2026, 2, 3818.18), _cumul(2026, 7, 3000.0)]})
    cdd = {"id": "emp-1", "contract_type": "CDD", "hire_date": "2026-07-01", "contract_end_date": "2026-09-30"}
    assert base_precarite_du_bulletin(cdd, 2026, 9, base)["brut_total_avant"] == 3818.18
    assert base_precarite_du_bulletin(cdd, 2026, 8, base) is None
    assert base_precarite_du_bulletin({**cdd, "contract_type": "CDI"}, 2026, 9, base) is None
