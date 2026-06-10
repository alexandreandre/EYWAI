"""
Intégration paie — chaîne timeline → prepare → calcul brut.

Vérifie le câblage métier attendu en production (mocks repository, pas de Supabase).
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.modules.payroll.application.salary_evolution_payroll import (
    prepare_salary_evolution_for_payslip,
)
from app.modules.payroll.engine.calcul_brut import calculer_salaire_brut

from tests.unit.payroll.helpers import build_test_contexte

pytestmark = pytest.mark.integration

EMPLOYEE_ID = "emp-integ-evo"
COMPANY_ID = "co-integ-evo"


def _calendrier_juin_2026() -> list:
    return [
        {
            "date_complete": date(2026, 6, d).isoformat(),
            "type": "travail_base",
            "heures": 7.0,
        }
        for d in range(1, 31)
        if date(2026, 6, d).weekday() < 5
    ]


@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_chaine_complete_prorata_et_rappel(mock_repo_cls, mock_sync):
    """Scénario prod : historique → prepare → contrat.json → bulletin."""
    timeline = [
        {
            "effective_date": "2026-03-01",
            "ancien_salaire": {"valeur": 2000},
            "nouveau_salaire": {"valeur": 2200},
        },
        {
            "effective_date": "2026-06-09",
            "ancien_salaire": {"valeur": 2200},
            "nouveau_salaire": {"valeur": 2400},
        },
    ]
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2400, "devise": "EUR"},
    }
    mock_repo.get_salary_history.return_value = timeline

    payload = prepare_salary_evolution_for_payslip(
        EMPLOYEE_ID, COMPANY_ID, 2026, 6
    )

    montant_prorata = round((2200 * 8 / 30) + (2400 * 22 / 30), 2)
    assert payload["salaire_de_base"]["valeur"] == pytest.approx(montant_prorata, abs=0.02)

    ctx = build_test_contexte(salaire_base=montant_prorata)
    rem = ctx.contrat.setdefault("remuneration", {})
    rem["salaire_de_base"] = payload["salaire_de_base"]
    rem["evolution_salaire_mois"] = payload["evolution_salaire_mois"]

    res = calculer_salaire_brut(
        ctx, _calendrier_juin_2026(), date(2026, 6, 1), date(2026, 6, 30)
    )

    gain_base = next(
        l["gain"]
        for l in res["lignes_composants_brut"]
        if (l.get("libelle") or "").startswith("Salaire de base")
    )
    rappel_gain = sum(
        l["gain"]
        for l in res["lignes_composants_brut"]
        if "Rappel" in (l.get("libelle") or "")
    )

    assert gain_base == pytest.approx(montant_prorata, abs=0.05)
    assert rappel_gain == pytest.approx(600.0, abs=0.05)
    assert res["salaire_brut_total"] == pytest.approx(
        montant_prorata + 600.0, abs=0.05
    )


@patch("app.modules.payroll.application.salary_evolution_payroll.sync_employee_salaire_actif")
@patch("app.modules.payroll.application.salary_evolution_payroll.EmployeeRepository")
def test_sync_salaire_actif_avant_resolution(mock_repo_cls, mock_sync):
    """La génération paie aligne la fiche avant de résoudre le bulletin."""
    mock_repo = MagicMock()
    mock_repo_cls.return_value = mock_repo
    mock_repo.get_by_id.return_value = {
        "id": EMPLOYEE_ID,
        "salaire_de_base": {"valeur": 2200},
    }
    mock_repo.get_salary_history.return_value = []

    prepare_salary_evolution_for_payslip(EMPLOYEE_ID, COMPANY_ID, 2026, 6)

    mock_sync.assert_called_once_with(EMPLOYEE_ID, COMPANY_ID, date.today())
