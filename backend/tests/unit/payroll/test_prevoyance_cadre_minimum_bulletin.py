"""Le bulletin d'un cadre sous 1,50 % de tranche A porte l'alerte, sans changer de montant (R-371)."""

from __future__ import annotations

import pytest

from app.modules.payroll.engine.calcul_cotisations import calculer_cotisations
from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.unit


def _prevoyance(patronal: float) -> dict:
    return {
        "prevoyance": {
            "adhesion": True,
            "lignes_specifiques": [
                {"libelle": "Prévoyance cadre", "patronal": patronal, "salarial": 0.0, "base": "brut_plafonne"}
            ],
        }
    }


def _codes(patronal: float, **kw) -> list:
    contexte = build_test_contexte(statut="Cadre", salaire_base=4500.0, specificites_extra=_prevoyance(patronal), **kw)
    contexte.alertes_baremes = []
    calculer_cotisations(contexte, 4500.0)
    return [a.get("code") for a in contexte.alertes_baremes if isinstance(a, dict)]


def test_sous_le_minimum_alerte_non_bloquante():
    contexte = build_test_contexte(statut="Cadre", salaire_base=4500.0, specificites_extra=_prevoyance(0.01155))
    contexte.alertes_baremes = []
    calculer_cotisations(contexte, 4500.0)
    alerte = next(a for a in contexte.alertes_baremes if a.get("code") == "prevoyance_cadre_sous_le_minimum")
    assert alerte["critique"] is False and alerte["severity"] == "warning"


def test_au_minimum_pas_d_alerte():
    assert "prevoyance_cadre_sous_le_minimum" not in _codes(0.015)


def test_l_alerte_ne_change_aucun_montant():
    avec = build_test_contexte(statut="Cadre", salaire_base=4500.0, specificites_extra=_prevoyance(0.01155))
    sans = build_test_contexte(statut="Cadre", salaire_base=4500.0, specificites_extra=_prevoyance(0.01155))
    avec.alertes_baremes = []
    sans.alertes_baremes = None
    assert calculer_cotisations(avec, 4500.0) == calculer_cotisations(sans, 4500.0)
