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


@patch(f"{_PROVIDERS}.process_payslip_generation")
@patch(f"{_PROVIDERS}.is_forfait_jour", return_value=False)
@patch(f"{_PROVIDERS}.employee_statut_reader")
def test_le_bac_a_sable_calcule_en_lecture_seule(_statut, _forfait, generer_heures):
    # Le pied du bulletin enregistrait le droit aux congés d'ancienneté
    # (`compute_and_persist_grant`) : la répétition de la DSN d'octobre (31/10)
    # l'a pris en écriture, et la vérification « À recalculer » écrivait en base.
    from app.core.lecture_seule import ecritures_permises

    vu = {}

    def generer(**_kwargs):
        vu["ecritures_permises"] = ecritures_permises()
        return {"status": "success", "payslip_data": {}}

    generer_heures.side_effect = generer
    payslip_generator_provider.generate_en_bac_a_sable("emp-1", 2026, 10)

    assert vu["ecritures_permises"] is False
    assert ecritures_permises() is True


@patch(f"{_PROVIDERS}.process_payslip_generation")
@patch(f"{_PROVIDERS}.is_forfait_jour", return_value=False)
@patch(f"{_PROVIDERS}.employee_statut_reader")
def test_dans_une_lecture_seule_le_bac_a_sable_garde_ses_lectures(_statut, _forfait, generer_heures):
    # Le brut d'une prime (lot 31) rejoue le bulletin dans un seul bloc : un bloc
    # neuf par essai relirait toute la base à chaque fois.
    from app.core import lecture_seule as module

    vu = {}

    def generer(**_kwargs):
        vu["bloc"] = module._EN_COURS.get()
        return {"status": "success", "payslip_data": {}}

    generer_heures.side_effect = generer
    with module.lecture_seule() as lectures:
        payslip_generator_provider.generate_en_bac_a_sable("emp-1", 2026, 10)

    assert vu["bloc"] is lectures
