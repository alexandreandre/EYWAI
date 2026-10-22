"""Les deux générateurs et les deux pipelines traitent la régularisation au même endroit."""

from __future__ import annotations

import inspect

import pytest

from app.modules.payroll.documents import (
    payslip_generator,
    payslip_generator_forfait,
    payslip_run_forfait,
    payslip_run_heures,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("module", [payslip_generator, payslip_generator_forfait])
def test_chaque_generateur_range_la_regularisation_avant_les_primes(module):
    source = inspect.getsource(module)
    assert "ranger_regularisation(row, saisies_data)" in source
    assert source.index("ranger_regularisation(row, saisies_data)") < source.index("est_saisie_ijss_validees(row)")


@pytest.mark.parametrize("module", [payslip_run_heures, payslip_run_forfait])
def test_chaque_pipeline_pose_les_regularisations_entre_la_reduction_et_le_net(module):
    source = inspect.getsource(module)
    pose = source.index("ajouter_regularisations(")
    assert source.index("calculer_reduction_generale(") < pose < source.index("resultats_nets = calculer_net_et_impot(")
    assert "regularisation_reduction_generale=effet_regul.reduction_generale" in source
