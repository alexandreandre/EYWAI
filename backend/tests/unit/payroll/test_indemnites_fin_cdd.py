"""Tests fin de CDD dans calculer_indemnites_sortie.

La précarité (art. L1243-8) est portée par le BULLETIN du dernier mois du
CDD : le moteur d'indemnités ne l'expose qu'à titre informatif et ne doit
JAMAIS l'ajouter aux totaux du STC (double versement sinon).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.engine.calcul_indemnites_sortie import (
    calculer_indemnites_sortie,
)

pytestmark = pytest.mark.unit


def _employee() -> dict:
    return {
        "id": "emp-1",
        "first_name": "Théo",
        "last_name": "Barberet",
        "hire_date": "2026-06-29",
        "contract_type": "CDD",
        "salaire_de_base": {"valeur": 1800.0},
    }


def _exit_data() -> dict:
    return {
        "id": "exit-1",
        "exit_type": "fin_cdd",
        "last_working_day": "2026-06-30",
        "notice_period_days": 0,
        "notice_indemnity_type": "not_applicable",
    }


@patch(
    "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
)
def test_fin_cdd_precarite_informative_hors_totaux(mock_conges):
    mock_conges.return_value = {
        "montant": 500.0,
        "description": "ICCP",
        "details": {"prime_precarite_incluse": 321.0},
    }

    res = calculer_indemnites_sortie(_employee(), _exit_data(), MagicMock())

    precarite = res["indemnite_precarite"]
    assert precarite["montant"] == 321.0
    assert precarite["versee_au_bulletin"] is True
    # Totaux = préavis (0) + congés (500) — précarité EXCLUE.
    assert res["total_gross_indemnities"] == 500.0


@patch(
    "app.modules.payroll.engine.calcul_indemnites_sortie.calculer_indemnite_conges_restants"
)
def test_fin_cdd_sans_precarite_estimee(mock_conges):
    """Précarité non estimée (ex. exclue via specificites_paie) : bloc à 0,
    et toujours rien dans les totaux."""
    mock_conges.return_value = {
        "montant": 200.0,
        "description": "ICCP",
        "details": {},
    }

    res = calculer_indemnites_sortie(_employee(), _exit_data(), MagicMock())

    assert res["indemnite_precarite"]["montant"] == 0.0
    assert res["total_gross_indemnities"] == 200.0
