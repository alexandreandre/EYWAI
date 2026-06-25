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

    def test_matricule_ok_when_payslip_name_order_differs(self):
        employees = [
            {
                "id": "e-mbc",
                "first_name": "Sammany",
                "last_name": "ADAM YOUSSEF",
                "email": "",
                "employee_folder_name": "ADAMYOUSSEF_Sammany",
            },
        ]
        roster = [RosterEmployee(id="e-mbc", first_name="Sammany", last_name="ADAM YOUSSEF")]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule="ADAMYOUSSE",
            email="",
            first_name="ADAM",
            last_name="YOUSSEF Sammany",
            full_name="ADAM YOUSSEF Sammany",
        )
        assert result["employee_id"] == "e-mbc"
        assert result["review_status"] == "ok"

    def test_patronymic_matches_dsn_last_name(self):
        employees = [
            {
                "id": "e-gros",
                "first_name": "Nadine",
                "last_name": "PRONIER",
                "email": "",
                "employee_folder_name": "PRONIER_Nadine",
            },
        ]
        roster = [RosterEmployee(id="e-gros", first_name="Nadine", last_name="PRONIER")]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule="GROS",
            email="",
            first_name="Nadine",
            last_name="GROS",
            full_name="GROS Nadine",
            patronymic_name="PRONIER",
        )
        assert result["employee_id"] == "e-gros"
        assert result["match_method"] == "patronymic"
        assert result["review_status"] == "ok"

    def test_matricule_warning_when_names_truly_diverge(self):
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule="BASTER",
            email="",
            first_name="Jean",
            last_name="DUPONT",
            full_name="Jean DUPONT",
        )
        assert result["employee_id"] == "e1"
        assert result["review_status"] == "warning"

    def test_compound_matricule_busiza_lus(self):
        employees = [
            {
                "id": "e-busiza",
                "first_name": "Serge",
                "last_name": "BUSIZA LUSELA",
                "email": "",
                "employee_folder_name": "BUSIZALUSELA_Serge",
            },
        ]
        roster = [RosterEmployee(id="e-busiza", first_name="Serge", last_name="BUSIZA LUSELA")]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule="BUSIZA LUS",
            email="",
            first_name="Serge",
            last_name="BUSIZA LUSELA",
            full_name="BUSIZA LUSELA Serge",
        )
        assert result["employee_id"] == "e-busiza"
        assert result["review_status"] == "ok"
