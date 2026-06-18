"""Tests unitaires du matching employé pour import pointages."""

from app.modules.schedules.application.employee_match import (
    is_junk_employee_name,
    resolve_employee_for_timesheet,
)
from app.modules.schedules.schemas.ai import RosterEmployee

ROSTER = [
    RosterEmployee(
        id="e1",
        first_name="Paul",
        last_name="Martin",
        time_tracking_id="196",
    ),
    RosterEmployee(
        id="e2",
        first_name="Sophie",
        last_name="Durand",
        time_tracking_id="270",
    ),
    RosterEmployee(id="e3", first_name="Rina", last_name="XHAFERI"),
    RosterEmployee(id="e4", first_name="Gérald", last_name="LIKA"),
    RosterEmployee(id="e5", first_name="Marie", last_name="Martin"),
    RosterEmployee(id="e6", first_name="Mir Naqibullah", last_name="MIRZADA"),
    RosterEmployee(id="e7", first_name="Mir Said Jan", last_name="MIRZADA"),
    RosterEmployee(
        id="e8",
        first_name="Mohamed",
        last_name="YOUSSEF",
        time_tracking_id="139",
    ),
    RosterEmployee(id="e9", first_name="Abderraouf", last_name="SPIGA"),
    RosterEmployee(id="e10", first_name="Kheireddine", last_name="SPIGA"),
]


class TestEmployeeMatch:
    def test_matricule_exact_high_confidence(self):
        p = resolve_employee_for_timesheet(
            raw_name="ADAM YOUSSEF", matricule="196", roster=ROSTER
        )
        assert p.employee_id == "e1"
        assert p.match_method == "matricule"
        assert p.review_status == "ok"

    def test_matricule_leading_zeros(self):
        p = resolve_employee_for_timesheet(
            raw_name="ADAM YOUSSEF", matricule="0196", roster=ROSTER
        )
        assert p.employee_id == "e1"

    def test_name_exact(self):
        p = resolve_employee_for_timesheet(
            raw_name="Durand Sophie", matricule=None, roster=ROSTER
        )
        assert p.employee_id == "e2"
        assert p.match_confidence == "high"

    def test_homonym_first_name_not_resolved(self):
        p = resolve_employee_for_timesheet(
            raw_name="Rina", matricule=None, roster=ROSTER
        )
        assert p.employee_id is None
        assert p.review_status == "error"

    def test_ambiguous_last_name(self):
        p = resolve_employee_for_timesheet(
            raw_name="Martin", matricule=None, roster=ROSTER
        )
        assert p.employee_id is None

    def test_lika_wrong_first_unique_last_name(self):
        p = resolve_employee_for_timesheet(
            raw_name="LIKA Rina", matricule="95", roster=ROSTER
        )
        assert p.employee_id == "e4"
        assert p.matched_name == "Gérald LIKA"
        assert any("Matricule 95" in w for w in p.warnings)

    def test_mirzada_disambiguated_by_first_name(self):
        p = resolve_employee_for_timesheet(
            raw_name="Mirzada Mir Nagibullah", matricule="243", roster=ROSTER
        )
        assert p.employee_id == "e6"

    def test_mirzada_said_jan(self):
        p = resolve_employee_for_timesheet(
            raw_name="MIRZADA Mir Said", matricule="150", roster=ROSTER
        )
        assert p.employee_id == "e7"

    def test_glued_last_name_mohamedyoussef(self):
        p = resolve_employee_for_timesheet(
            raw_name="MOHAMEDYOUSSEF Mohamed", matricule="139", roster=ROSTER
        )
        assert p.employee_id == "e8"

    def test_spiga_typo_first_name(self):
        p = resolve_employee_for_timesheet(
            raw_name="SPIGA Abdelraouf", matricule="244", roster=ROSTER
        )
        assert p.employee_id == "e9"

    def test_junk_ocr_line(self):
        assert is_junk_employee_name("Édition en heures et minutes")
        p = resolve_employee_for_timesheet(
            raw_name="Édition en heures et minutes",
            matricule="1616",
            roster=ROSTER,
        )
        assert p.employee_id is None
        assert p.review_status == "error"
