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
            "last_name": "CAVUBEL",
            "nir": "1800175202456",
            "email": "import@test.dsn-import.local",
        }
    ]
    roster = [
        RosterEmployee(id="emp-1", first_name="Lahouari", last_name="CAVUBEL")
    ]
    match = resolve_payroll_export_row_match(
        roster=roster,
        employees=employees,
        nir="180017520245618",
        matricule="",
        email="",
        first_name="Lahouari",
        last_name="CAVUBEL",
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
            "last_name": "DUMILLY",
            "nir": "1800175208456",
            "email": "lucas@test.dsn-import.local",
        }
    ]
    match = resolve_payroll_export_row_match(
        roster=[],
        employees=employees,
        nir="180017520845632",
        matricule="",
        email="",
        first_name="Lucas",
        last_name="DUMILLY",
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
