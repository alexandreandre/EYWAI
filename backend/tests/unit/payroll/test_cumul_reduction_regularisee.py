"""Le cumul de la réduction générale enregistre ce qui a été réellement appliqué."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.modules.payroll.documents.payslip_run_common import mettre_a_jour_cumuls
from app.modules.payroll.engine.corrections_manuelles import RegularisationInvalide

pytestmark = pytest.mark.unit


def _contexte(cumul_rg: float) -> SimpleNamespace:
    return SimpleNamespace(
        cumuls={"cumuls": {"reduction_generale_patronale": cumul_rg, "brut_total": 1000.0}, "periode": {}},
        company_id=None,
        year=2026,
    )


def _cumuls(tmp_path, contexte, ligne_rg, regul, mois=10):
    mettre_a_jour_cumuls(
        contexte,
        2000.0,
        0.0,
        {"net_imposable": 1500.0},
        ligne_rg,
        mois,
        0.0,
        0.0,
        tmp_path,
        regularisation_reduction_generale=regul,
    )
    return json.loads((tmp_path / "cumuls" / f"{mois:02d}.json").read_text(encoding="utf-8"))["cumuls"]


def test_la_regularisation_entre_dans_le_cumul_de_la_reduction(tmp_path):
    cumuls = _cumuls(tmp_path, _contexte(-900.0), {"valeur_cumulative_a_enregistrer": 1000.0}, -12.5)
    assert cumuls["reduction_generale_patronale"] == -1012.5


def test_sans_ligne_de_reduction_ce_mois_le_cumul_precedent_est_regularise(tmp_path):
    cumuls = _cumuls(tmp_path, _contexte(-900.0), None, 20.0)
    assert cumuls["reduction_generale_patronale"] == -880.0


def test_sans_regularisation_le_cumul_est_celui_d_avant(tmp_path):
    cumuls = _cumuls(tmp_path, _contexte(-900.0), {"valeur_cumulative_a_enregistrer": 1000.0}, 0.0)
    assert cumuls["reduction_generale_patronale"] == -1000.0


def test_une_reduction_annuelle_negative_est_refusee(tmp_path):
    with pytest.raises(RegularisationInvalide):
        _cumuls(tmp_path, _contexte(-10.0), None, 25.0)
