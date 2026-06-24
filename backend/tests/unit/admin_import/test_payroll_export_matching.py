"""Tests rapprochement NIR export paie."""

from app.modules.admin_import.application.payroll_export_matching import (
    resolve_payroll_export_row_match,
)
from app.modules.schedules.schemas.ai import RosterEmployee


def test_match_by_nir():
    employees = [
        {
            "id": "emp-1",
            "first_name": "Lahouari",
            "last_name": "BOUDJEMAA",
            "nir": "1610999352308",
            "email": "import@test.dsn-import.local",
        }
    ]
    roster = [
        RosterEmployee(id="emp-1", first_name="Lahouari", last_name="BOUDJEMAA")
    ]
    match = resolve_payroll_export_row_match(
        roster=roster,
        employees=employees,
        nir="161099935230854",
        matricule="",
        email="",
        first_name="Lahouari",
        last_name="BOUDJEMAA",
    )
    assert match["employee_id"] == "emp-1"
    assert match["match_method"] == "nir"
    assert match["review_status"] == "ok"
    assert not any("NIR présent" in w for w in match.get("warnings") or [])


def test_name_match_without_nir_warning_when_nir_resolves():
    employees = [
        {
            "id": "emp-1",
            "first_name": "Lucas",
            "last_name": "CHAMBERT",
            "nir": "1990626198055",
            "email": "lucas@test.dsn-import.local",
        }
    ]
    match = resolve_payroll_export_row_match(
        roster=[],
        employees=employees,
        nir="199062619805541",
        matricule="",
        email="",
        first_name="Lucas",
        last_name="CHAMBERT",
    )
    assert match["employee_id"] == "emp-1"
    assert match["match_method"] == "nir"


def test_no_match_enrich_only():
    match = resolve_payroll_export_row_match(
        roster=[],
        employees=[],
        nir="999999999999999",
        matricule="",
        email="",
        first_name="Inconnu",
        last_name="TEST",
    )
    assert match["employee_id"] is None
    assert match["review_status"] == "error"
