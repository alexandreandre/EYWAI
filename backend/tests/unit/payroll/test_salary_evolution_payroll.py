"""Tests prepare_salary_evolution_for_payslip — résolution avant génération bulletin."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.application.salary_evolution_payroll import (
    prepare_salary_evolution_for_payslip,
)

pytestmark = pytest.mark.unit

EMPLOYEE_ID = "emp-salary-evo"
COMPANY_ID = "co-salary-evo"


def _timeline_entry(eff: str, ancien: float, nouveau: float) -> dict:
    return {
        "effective_date": eff,
        "ancien_salaire": {"valeur": ancien},
        "nouveau_salaire": {"valeur": nouveau},
    }


@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_prorata_mi_mois(mock_repo_cls, mock_sync):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2600, "devise": "EUR"},
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-06-09", 2600, 2678),
    ]

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    mock_sync.assert_called_once_with(EMPLOYEE_ID, COMPANY_ID, date.today())
    attendu = round((2600 * 8 / 30) + (2678 * 22 / 30), 2)
    assert result["salaire_de_base"]["valeur"] == pytest.approx(attendu, abs=0.02)
    evo = result["evolution_salaire_mois"]
    assert evo["prorata"] is not None
    assert evo["prorata"]["jours_ancien"] == 8
    assert evo["rappel"]["montant"] == 0.0


@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_rappel_et_salaire_plein(mock_repo_cls, mock_sync):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2200},
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-03-01", 2000, 2200),
    ]

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    assert result["salaire_de_base"]["valeur"] == 2200.0
    assert result["evolution_salaire_mois"]["rappel"]["montant"] == pytest.approx(
        600.0, abs=0.02
    )


@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_date_future_n_impacte_pas_bulletin(mock_repo_cls, mock_sync):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2200},
    }
    mock_repo.get_salary_history.return_value = [
        _timeline_entry("2026-07-01", 2200, 2500),
    ]

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    assert result["salaire_de_base"]["valeur"] == 2200.0
    assert result["evolution_salaire_mois"]["prorata"] is None
    assert result["evolution_salaire_mois"]["rappel"]["montant"] == 0.0


@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_prepare_employe_introuvable(mock_repo_cls, mock_sync):
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = None

    result = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    assert result == {}
    mock_sync.assert_called_once()
