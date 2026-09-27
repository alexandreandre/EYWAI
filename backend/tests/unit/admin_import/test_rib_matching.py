"""Tests unitaires — rapprochement salarié import RIB."""

from app.modules.admin_import.application.rib_matching import (
    _match_by_payroll_matricule,
    resolve_rib_row_match,
)
from app.modules.schedules.schemas.ai import RosterEmployee

EMPLOYEES = [
    {
        "id": "e1",
        "first_name": "Ferurat",
        "last_name": "BARENAC",
        "email": "",
        "employee_folder_name": "BARENAC_Ferurat",
    },
    {
        "id": "e2",
        "first_name": "Quentin",
        "last_name": "DUMINET",
        "email": "",
        "employee_folder_name": "DUMINET_Quentin",
    },
]

ROSTER = [
    RosterEmployee(id="e1", first_name="Ferurat", last_name="BARENAC"),
    RosterEmployee(id="e2", first_name="Quentin", last_name="DUMINET"),
]


class TestPayrollMatriculeMatch:
    def test_exact_last_name(self):
        assert _match_by_payroll_matricule("BARENAC", EMPLOYEES)["id"] == "e1"

    def test_truncated_last_name(self):
        assert _match_by_payroll_matricule("DUMINE", EMPLOYEES)["id"] == "e2"


class TestResolveRibRowMatch:
    def test_matches_by_matricule_and_name(self):
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule="BARENAC",
            email="",
            first_name="Ferurat",
            last_name="BARENAC",
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
            full_name="Ferurat BARENAC",
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
                "last_name": "BELILLY",
                "email": "",
                "employee_folder_name": "BELILLY_Nadine",
            },
        ]
        roster = [RosterEmployee(id="e-gros", first_name="Nadine", last_name="BELILLY")]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule="GROS",
            email="",
            first_name="Nadine",
            last_name="GROS",
            full_name="GROS Nadine",
            patronymic_name="BELILLY",
        )
        assert result["employee_id"] == "e-gros"
        assert result["match_method"] == "patronymic"
        assert result["review_status"] == "ok"

    def test_matricule_warning_when_names_truly_diverge(self):
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule="BARENAC",
            email="",
            first_name="Jean",
            last_name="DUPONT",
            full_name="Jean DUPONT",
        )
        assert result["employee_id"] == "e1"
        assert result["review_status"] == "warning"

    def test_compound_matricule_dumouin_lus(self):
        employees = [
            {
                "id": "e-dumouin",
                "first_name": "Serge",
                "last_name": "DUMOUIN TALOUIN",
                "email": "",
                "employee_folder_name": "BUSIZALUSELA_Serge",
            },
        ]
        roster = [RosterEmployee(id="e-dumouin", first_name="Serge", last_name="DUMOUIN TALOUIN")]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule="DUMOUIN LUS",
            email="",
            first_name="Serge",
            last_name="DUMOUIN TALOUIN",
            full_name="DUMOUIN TALOUIN Serge",
        )
        assert result["employee_id"] == "e-dumouin"
        assert result["review_status"] == "ok"
