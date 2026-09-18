"""Le provider sait générer en bac à sable, heures comme forfait."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.modules.payroll.documents.bac_a_sable import BacASable
from app.modules.payslips.infrastructure.providers import payslip_generator_provider

pytestmark = pytest.mark.unit

_PROVIDERS = "app.modules.payslips.infrastructure.providers"


@patch(f"{_PROVIDERS}.process_payslip_generation_forfait")
@patch(f"{_PROVIDERS}.process_payslip_generation")
@patch(f"{_PROVIDERS}.is_forfait_jour", return_value=False)
@patch(f"{_PROVIDERS}.employee_statut_reader")
def test_heures_recoit_le_bac_a_sable(_statut, _forfait, generer_heures, generer_forfait):
    generer_heures.return_value = {"status": "success", "payslip_data": {}}

    payslip_generator_provider.generate_en_bac_a_sable(
        "emp-1", 2026, 2, cumuls_precedents={"cumuls": {"brut_total": 3000.0}}
    )

    generer_heures.assert_called_once_with(
        employee_id="emp-1", year=2026, month=2,
        bac_a_sable=BacASable(cumuls_precedents={"cumuls": {"brut_total": 3000.0}}),
    )
    generer_forfait.assert_not_called()


@patch(f"{_PROVIDERS}.process_payslip_generation_forfait")
@patch(f"{_PROVIDERS}.process_payslip_generation")
@patch(f"{_PROVIDERS}.is_forfait_jour", return_value=True)
@patch(f"{_PROVIDERS}.employee_statut_reader")
def test_forfait_recoit_le_bac_a_sable(_statut, _forfait, generer_heures, generer_forfait):
    generer_forfait.return_value = {"status": "success", "payslip_data": {}}

    payslip_generator_provider.generate_en_bac_a_sable("emp-2", 2026, 1)

    generer_forfait.assert_called_once_with(
        employee_id="emp-2", year=2026, month=1, bac_a_sable=BacASable(),
    )
    generer_heures.assert_not_called()
