"""Calcul de janvier : aperçu des droits JTC de l'année, avant application."""

from app.modules.absences.application.leave_settings_commands import (
    build_jtc_annual_run,
)
from app.modules.absences.domain.leave_policy import LeavePolicySettings


ACTIVE = LeavePolicySettings(jtc_enabled=True)


def _employee(emp_id: str, hire: str, exit_date: str | None = None) -> dict:
    return {
        "id": emp_id,
        "first_name": "Test",
        "last_name": emp_id.upper(),
        "hire_date": hire,
        "exit_date": exit_date,
    }


def test_apercu_du_droit_dune_annee_complete():
    """Droit 2027 calculé sur 2026 : présence pleine → 3 JTC."""
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[_employee("a", "2015-03-01")],
        absence_days_by_employee={},
        policy=ACTIVE,
    )
    assert len(rows) == 1
    assert rows[0].acquired_days == 3
    assert rows[0].absence_days == 0


def test_apercu_proratise_lentree_de_lannee_de_reference():
    """Entré le 01/07/2026, droit 2027 calculé sur 2026 → 1 JTC."""
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[_employee("a", "2026-07-01")],
        absence_days_by_employee={},
        policy=ACTIVE,
    )
    assert rows[0].acquired_days == 1


def test_apercu_tient_compte_des_absences():
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[_employee("a", "2015-03-01")],
        absence_days_by_employee={"a": 120},
        policy=ACTIVE,
    )
    assert rows[0].absence_days == 120
    assert rows[0].acquired_days == 2


def test_societe_non_activee_ne_produit_aucune_ligne():
    rows = build_jtc_annual_run(
        company_id="cartol",
        target_year=2027,
        employees=[_employee("a", "2015-03-01")],
        absence_days_by_employee={},
        policy=LeavePolicySettings(),
    )
    assert rows == []


def test_salarie_sans_date_dembauche_est_ignore():
    rows = build_jtc_annual_run(
        company_id="mbc",
        target_year=2027,
        employees=[{"id": "a", "first_name": "X", "last_name": "Y", "hire_date": None}],
        absence_days_by_employee={},
        policy=ACTIVE,
    )
    assert rows == []
