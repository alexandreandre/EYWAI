"""Indemnité de fin de CDD : sa base est toute la rémunération du contrat.

Code du travail, L1243-8 : l'indemnité de fin de contrat « est égale à 10 % de
la rémunération totale brute versée au salarié » (au titre du contrat,
renouvellements compris, puisqu'un renouvellement ne crée pas de contrat).
Audit du 03/11/2026 (lot F, verdicts 2 et 3) : l'ancien logiciel prenait une
base tronquée (un mois omis, un seul mois retenu) ou y mettait un contrat
précédent (un CDI de janvier-février dans la base d'un CDD de juin-septembre).

Martine prenait le cumul `brut_total` du mois d'avant : le cumul de l'année
civile pour un mois repris de l'ancien logiciel, qui porte un contrat précédent
de l'année et oublie les mois d'une année précédente. La base est maintenant
la somme des bulletins du contrat de la fiche, de son premier mois au mois
d'avant, plus le brut du mois ; s'il manque un bulletin, le cumul reste, et
le bulletin le dit.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll.engine.calcul_brut import _calculer_prime_precarite_cdd
from app.modules.payroll.engine.reference_remuneration import brut_du_contrat_avant_le_mois
from tests.unit.base_en_memoire import BaseEnMemoire
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _bulletin(annee, mois, brut, contrat=None):
    return {
        "employee_id": "emp-1",
        "year": annee,
        "month": mois,
        "contract_period_id": contrat,
        "payslip_data": {"salaire_brut": brut},
    }


def test_la_somme_des_bulletins_du_contrat_du_premier_mois_au_mois_d_avant():
    base = BaseEnMemoire({
        "payslips": [
            _bulletin(2026, 2, 3000.0),  # un CDI d'avant, rangé avec son contrat
            _bulletin(2026, 2, 3000.0, contrat="cdi-1"),
            _bulletin(2026, 6, 272.73),
            _bulletin(2026, 7, 3000.0),
            _bulletin(2026, 8, 3000.0),
        ]
    })
    resultat = brut_du_contrat_avant_le_mois("emp-1", date(2026, 6, 29), 2026, 9, base)
    assert resultat == {"montant": 6272.73, "mois_sans_bulletin": []}


def test_un_contrat_sur_deux_annees_compte_l_annee_d_avant():
    base = BaseEnMemoire({"payslips": [_bulletin(2025, 11, 1800.0), _bulletin(2025, 12, 1800.0), _bulletin(2026, 1, 1850.0)]})
    resultat = brut_du_contrat_avant_le_mois("emp-1", date(2025, 11, 3), 2026, 2, base)
    assert resultat["montant"] == 5450.0
    assert resultat["mois_sans_bulletin"] == []


def test_un_mois_sans_bulletin_est_nomme():
    base = BaseEnMemoire({"payslips": [_bulletin(2026, 4, 1598.66), _bulletin(2026, 6, 517.40)]})
    resultat = brut_du_contrat_avant_le_mois("emp-1", date(2026, 4, 7), 2026, 7, base)
    assert resultat["mois_sans_bulletin"] == ["05/2026"]


def test_le_premier_mois_du_contrat_n_a_rien_avant():
    resultat = brut_du_contrat_avant_le_mois("emp-1", date(2026, 9, 2), 2026, 9, BaseEnMemoire({}))
    assert resultat == {"montant": 0.0, "mois_sans_bulletin": []}


def _cdd_de_septembre(base_du_contrat, brut_total=13090.90 - 3000.0):
    ctx = build_test_contexte(
        type_contrat="CDD",
        date_entree="2026-06-29",
        date_fin_contrat="2026-09-30",
        cumuls={"brut_total": brut_total},
    )
    if base_du_contrat is not None:
        ctx.contrat["contrat"]["brut_du_contrat_avant_le_mois"] = base_du_contrat
    return ctx


def test_la_base_est_celle_des_bulletins_du_contrat_pas_le_cumul():
    """Le cas de l'audit : 9 272,73 € de CDD, 3 818,18 € de CDI d'avant dans le cumul."""
    ctx = _cdd_de_septembre({"montant": 6272.73, "mois_sans_bulletin": []})
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 927.27


def test_sans_bulletin_pour_un_mois_le_cumul_reste_et_c_est_dit():
    ctx = _cdd_de_septembre({"montant": 3272.73, "mois_sans_bulletin": ["07/2026"]})
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 1309.09
    alertes = [a for a in ctx.alertes_baremes if a.get("code") == "precarite_base_incomplete"]
    assert alertes and "07/2026" in alertes[0]["message"]


def test_sans_lecture_des_bulletins_le_cumul_d_avant():
    ctx = _cdd_de_septembre(None)
    ligne = _calculer_prime_precarite_cdd(ctx, 3000.0, date(2026, 9, 1), date(2026, 9, 30))
    assert ligne["gain"] == 1309.09


def test_le_bulletin_lit_la_base_seulement_au_dernier_mois_d_un_cdd():
    from app.modules.payroll.engine.reference_remuneration import base_precarite_du_bulletin

    base = BaseEnMemoire({"payslips": [_bulletin(2026, 7, 3000.0), _bulletin(2026, 8, 3000.0)]})
    cdd = {"id": "emp-1", "contract_type": "CDD", "hire_date": "2026-07-01", "contract_end_date": "2026-09-30"}
    assert base_precarite_du_bulletin(cdd, 2026, 9, base) == {"montant": 6000.0, "mois_sans_bulletin": []}
    assert base_precarite_du_bulletin(cdd, 2026, 8, base) is None
    assert base_precarite_du_bulletin({**cdd, "contract_type": "CDI"}, 2026, 9, base) is None
