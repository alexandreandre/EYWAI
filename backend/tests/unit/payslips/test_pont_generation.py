"""La génération de l'écran traverse le vrai pont partagé jusqu'au générateur.

Le 01/11/2026, toute génération tombait en 500 sur le site de test : le provider
passait `contract_period_id` (D3) au pont `payslip_services`, qui ne le prenait
pas. Les autres tests remplacent le pont ; ceux-ci ne remplacent que le
générateur au bout.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payslips.infrastructure.providers import payslip_generator_provider

pytestmark = pytest.mark.unit

_HEURES = "app.modules.payroll.documents.payslip_generator.process_payslip_generation"
_FORFAIT = "app.modules.payroll.documents.payslip_generator_forfait.process_payslip_generation_forfait"


@pytest.mark.parametrize("periode", [None, "periode-1"])
def test_le_bulletin_aux_heures_arrive_au_generateur(periode):
    with patch(_HEURES, return_value={"status": "success"}) as generateur:
        payslip_generator_provider.generate_heures("emp-1", 2026, 10, contract_period_id=periode)

    assert generateur.call_args.kwargs["contract_period_id"] == periode
    assert generateur.call_args.kwargs["employee_id"] == "emp-1"


@pytest.mark.parametrize("periode", [None, "periode-2"])
def test_le_bulletin_au_forfait_arrive_au_generateur(periode):
    with patch(_FORFAIT, return_value={"status": "success"}) as generateur:
        payslip_generator_provider.generate_forfait("emp-2", 2026, 10, contract_period_id=periode)

    assert generateur.call_args.kwargs["contract_period_id"] == periode


def test_le_depart_a_zero_suit_toujours():
    choix = {"par": "rh-1", "le": "2026-11-01"}
    with patch(_HEURES, return_value={"status": "success"}) as generateur:
        payslip_generator_provider.generate_heures("emp-1", 2026, 10, depart_a_zero=choix)

    assert generateur.call_args.kwargs["depart_a_zero"] == choix
