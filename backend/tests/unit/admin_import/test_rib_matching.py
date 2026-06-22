"""Tests unitaires — rapprochement salarié import RIB."""

from app.modules.admin_import.application.rib_matching import (
    _match_by_payroll_matricule,
    resolve_rib_row_match,
)
from app.modules.schedules.schemas.ai import RosterEmployee

EMPLOYEES = [
    {
        "id": "e1",
        "first_name": "Damien",
        "last_name": "BASTER",
        "email": "",
        "employee_folder_name": "BASTER_Damien",
    },
    {
        "id": "e2",
        "first_name": "Quentin",
        "last_name": "BRISMONTIER",
        "email": "",
        "employee_folder_name": "BRISMONTIER_Quentin",
    },
]

ROSTER = [
    RosterEmployee(id="e1", first_name="Damien", last_name="BASTER"),
    RosterEmployee(id="e2", first_name="Quentin", last_name="BRISMONTIER"),
]


class TestPayrollMatriculeMatch:
    def test_exact_last_name(self):
        assert _match_by_payroll_matricule("BASTER", EMPLOYEES)["id"] == "e1"

    def test_truncated_last_name(self):
        assert _match_by_payroll_matricule("BRISMONTIE", EMPLOYEES)["id"] == "e2"


class TestResolveRibRowMatch:
    def test_matches_by_matricule_and_name(self):
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule="BASTER",
            email="",
            first_name="Damien",
            last_name="BASTER",
            full_name="",
        )
        assert result["employee_id"] == "e1"
        assert result["review_status"] == "ok"

    def test_matches_full_name_column(self):
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule="",
            email="",
            first_name="",
            last_name="",
            full_name="Damien BASTER",
        )
        assert result["employee_id"] == "e1"
