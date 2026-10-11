"""Réduction Fillon (périodes avant 2026) : le FNAL du paramètre T suit
l'effectif du contexte. Il lisait `entreprise["effectif"]`, clé qui n'existe
pas (l'effectif est dans `parametres_paie`) : le FNAL était toujours pris
« moins de 50 » (enquête du 10/10/2026)."""

from types import SimpleNamespace

import pytest

from app.modules.payroll.engine.calcul_reduction_generale import _calculer_parametre_T

pytestmark = pytest.mark.unit

_BAREMES = {
    "cotisations": {
        "cotisations": [
            {"id": "fnal", "patronal": {"taux_50_et_plus": 0.005, "taux_moins_50": 0.001}}
        ]
    }
}


def _contexte(effectif):
    return SimpleNamespace(
        baremes=_BAREMES,
        entreprise={"parametres_paie": {"effectif": effectif, "taux_at_mp": 0.0}},
        effectif=effectif,
    )


def test_au_dela_de_50_salaries_le_fnal_est_a_0_50():
    assert _calculer_parametre_T(_contexte(70)) == pytest.approx(0.005)


def test_sous_50_salaries_le_fnal_est_a_0_10():
    assert _calculer_parametre_T(_contexte(12)) == pytest.approx(0.001)
