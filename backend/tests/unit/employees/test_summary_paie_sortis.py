"""Liste paie (status=payroll) : un salarié parti y figure s'il a une sortie datée.

Demory (Colorplast) est sorti le 24/07/2026 : il doit apparaître sur juin
(bulletin existant) et juillet (solde de tout compte). La liste porte donc
`exit_last_working_day`, et l'écran filtre mois par mois.
"""

from unittest.mock import patch

import pytest

from app.modules.employees.application import queries

pytestmark = pytest.mark.unit

_Q = "app.modules.employees.application.queries"


def _rows():
    return [
        {"id": "actif", "employment_status": "actif"},
        {"id": "demory", "employment_status": "parti"},
        {"id": "sans-sortie", "employment_status": "parti"},
    ]


@patch(f"{_Q}._bulk_exit_last_working_days")
@patch(f"{_Q}._employee_repository")
def test_liste_paie_garde_les_sortis_dates_et_porte_leur_dernier_jour(repo, bulk):
    repo.get_summary_by_company.return_value = _rows()
    bulk.return_value = {"demory": "2026-07-24"}

    rows = queries.get_employees_summary("co-1", payroll_ready_only=True)

    by_id = {r["id"]: r for r in rows}
    assert set(by_id) == {"actif", "demory"}
    assert by_id["demory"]["exit_last_working_day"] == "2026-07-24"
    assert by_id["actif"]["exit_last_working_day"] is None


@patch(f"{_Q}._bulk_exit_last_working_days")
@patch(f"{_Q}._employee_repository")
def test_liste_simple_sans_filtre_paie_inchangee(repo, bulk):
    repo.get_summary_by_company.return_value = _rows()

    rows = queries.get_employees_summary("co-1")

    assert [r["id"] for r in rows] == ["actif", "demory", "sans-sortie"]
    bulk.assert_not_called()
