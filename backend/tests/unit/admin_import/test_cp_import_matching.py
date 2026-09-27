"""Tests rapprochement import CP (matricule tronqué, noms OCR absurdes)."""

from app.modules.admin_import.application.cp_import import _flag_duplicate_employee_matches
from app.modules.admin_import.application.cp_payslip_parser import parse_payslip_page_text
from app.modules.admin_import.application.rib_matching import resolve_rib_row_match
from app.modules.schedules.schemas.ai import RosterEmployee

DUMOUIN_PAGE = """
   COMITECH                                                                            BULLETIN DE SALAIRE
   Période : Mai 2026
   Siret : 49861035100013         Code NAF: 2229A
                  CP N-1         CP N
                                                                                  Mr DUMOUIN TALOUIN Serge
  Acquis :        24.00 /      24.96 /
  Total pris :    24.00 /      13.00 /
  Solde :          0.00 /      11.96 /
   Matricule : DUMOUIN LUS              NoSécu.: 180017520345685
"""

JUNK_NAME_PAGE = """
   COMITECH                                                                            BULLETIN DE SALAIRE
   Période : Mai 2026
   Siret : 49861035100013         Code NAF: 2229A
                  CP N-1         CP N
                                                                                  Mr de présence 24.00
  Acquis :        18.00 /      24.96 /
  Total pris :    18.00 /      13.00 /
  Solde :          0.00 /      11.96 /
   Matricule : GUENAI              NoSécu.: 180017520345685
"""

EMPLOYEES = [
    {
        "id": "e-dumouin",
        "first_name": "Serge",
        "last_name": "DUMOUIN TALOUIN",
        "email": "",
        "employee_folder_name": "BUSIZALUSELA_Serge",
    },
    {
        "id": "e-debarros",
        "first_name": "Grégory",
        "last_name": "DE BAROCHE",
        "email": "",
        "employee_folder_name": "DEBARROS_Gregory",
    },
]

ROSTER = [
    RosterEmployee(id="e-dumouin", first_name="Serge", last_name="DUMOUIN TALOUIN"),
    RosterEmployee(id="e-debarros", first_name="Grégory", last_name="DE BAROCHE"),
]


class TestCpPayslipNameExtraction:
    def test_prefers_name_aligned_with_matricule(self):
        parsed = parse_payslip_page_text(DUMOUIN_PAGE)
        assert parsed.matricule == "DUMOUIN LUS"
        assert parsed.raw_name == "DUMOUIN TALOUIN Serge"

    def test_rejects_junk_presence_name(self):
        parsed = parse_payslip_page_text(JUNK_NAME_PAGE)
        assert parsed.matricule == "GUENAI"
        assert parsed.raw_name is None


class TestCpImportMatching:
    def test_dumouin_lus_matches_compound_last_name(self):
        parsed = parse_payslip_page_text(DUMOUIN_PAGE)
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule=parsed.matricule or "",
            email="",
            first_name="Serge",
            last_name="DUMOUIN TALOUIN",
            full_name=parsed.raw_name or "",
            strict_matricule_fallback=True,
        )
        assert result["employee_id"] == "e-dumouin"
        assert result["review_status"] == "ok"

    def test_unknown_matricule_does_not_fuzzy_match_de(self):
        parsed = parse_payslip_page_text(JUNK_NAME_PAGE)
        result = resolve_rib_row_match(
            roster=ROSTER,
            employees=EMPLOYEES,
            matricule=parsed.matricule or "",
            email="",
            first_name="",
            last_name="",
            full_name=parsed.raw_name or "",
            strict_matricule_fallback=True,
        )
        assert result["employee_id"] is None
        assert result["review_status"] == "error"
        assert any("GUENAI" in warning for warning in result["warnings"])

    def test_time_tracking_id_matricule_matches(self):
        employees = [
            {
                "id": "e-verague",
                "first_name": "Mir Said Jan",
                "last_name": "VERAGUE",
                "time_tracking_id": "VERAGUE2",
            }
        ]
        roster = [
            RosterEmployee(
                id="e-verague",
                first_name="Mir Said Jan",
                last_name="VERAGUE",
                time_tracking_id="VERAGUE2",
            )
        ]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule="VERAGUE2",
            email="",
            first_name="",
            last_name="",
            full_name="panier soumises 2.50 15.0000",
            strict_matricule_fallback=True,
        )
        assert result["employee_id"] == "e-verague"
        assert result["review_status"] == "ok"
        assert result["match_method"] == "matricule"

    def test_junk_name_does_not_block_matricule_match(self):
        parsed = parse_payslip_page_text(
            """
   MONT BLANC COMPOSITE                                                                       BULLETIN DE SALAIRE
   Période : Mai 2026
   Siret : 75116833700028
                 CP N-1         CP N
                                                     M. Assiduité Atelier 50.00
  Acquis :        30.00 /      25.96 /
  Solde :          0.00 /      12.96 /
   Matricule : BOUSSANOR              NoSécu.: 180017520345685
"""
        )
        employees = [
            {
                "id": "e-bouss",
                "first_name": "Mohamed",
                "last_name": "BOUSSANOR",
                "time_tracking_id": "BOUSSANOR",
            }
        ]
        roster = [
            RosterEmployee(
                id="e-bouss",
                first_name="Mohamed",
                last_name="BOUSSANOR",
                time_tracking_id="BOUSSANOR",
            )
        ]
        result = resolve_rib_row_match(
            roster=roster,
            employees=employees,
            matricule=parsed.matricule or "",
            email="",
            first_name="",
            last_name="",
            full_name=parsed.raw_name or "",
            strict_matricule_fallback=True,
        )
        assert parsed.raw_name is None
        assert result["employee_id"] == "e-bouss"
        assert result["review_status"] == "ok"


class TestCpDuplicateEmployeeFlag:
    def test_flags_multiple_rows_same_employee(self):
        rows = [
            {"row_index": 1, "employee_id": "e1", "review_status": "ok", "warnings": []},
            {"row_index": 2, "employee_id": "e1", "review_status": "ok", "warnings": []},
            {"row_index": 3, "employee_id": "e2", "review_status": "ok", "warnings": []},
        ]
        conflicts = _flag_duplicate_employee_matches(rows)
        assert conflicts == 1
        assert rows[0]["review_status"] == "error"
        assert rows[0]["duplicate_employee_conflict"] is True
        assert rows[2]["review_status"] == "ok"
