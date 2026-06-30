"""Tests parseur Cegid tableau horizontal."""

from app.modules.schedules.application.parsers.cegid_horizontal import (
    is_cegid_horizontal_format,
    try_parse_cegid_horizontal,
)

HORIZONTAL_SAMPLE = """
Pointages "retenu"
Du 27/04/2026 au 03/05/2026
Lundi 27/04/26 Mardi 28/04/26 Mercredi 29/04/26 Jeudi 30/04/26 Vendredi 01/05/26
196 ADAM YOUSSEF 7:30 7:29 7:30 7:30 7:30 Total pour la semaine 18/2026: 37:29
270 DURAND Sophie 0:00 7:00 7:00 7:00 7:00 Total pour la semaine 18/2026: 28:00
"""


class TestCegidHorizontalFormat:
    def test_detects_horizontal_table(self):
        assert is_cegid_horizontal_format(HORIZONTAL_SAMPLE)

    def test_rejects_vertical_blocks(self):
        vertical = """
Pointages "retenu"
Du 25/05/2026 au 31/05/2026
196 ADAM YOUSSEF
Lundi 25/05/26
# 7:30
Total pour la semaine 22/2026: 37:29
"""
        assert not is_cegid_horizontal_format(vertical)


class TestCegidHorizontalParse:
    def test_parses_employee_rows(self):
        result = try_parse_cegid_horizontal(
            HORIZONTAL_SAMPLE, target_year=2026, target_month=4
        )
        assert result.format_detected
        assert result.confidence >= 0.75
        assert len(result.employees) == 2
        adam = next(e for e in result.employees if e.matricule == "196")
        assert len(adam.days) == 4
        assert adam.days[0].jour == 27
        assert result.week_number == 18
