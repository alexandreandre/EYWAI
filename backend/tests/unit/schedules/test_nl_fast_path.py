"""Tests de l'analyse déterministe rapide (sans LLM) du remplissage calendrier."""

from app.modules.schedules.application.nl_fast_path import try_fast_parse_instruction
from app.modules.schedules.schemas.ai import RosterEmployee

ROSTER = [
    RosterEmployee(id="e1", first_name="Paul", last_name="Martin"),
    RosterEmployee(id="e2", first_name="Sophie", last_name="Durand"),
]


class TestTryFastParseInstruction:
    def test_weekday_range_with_hours(self):
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="Paul Martin a fait 8h du lundi au jeudi",
            roster=ROSTER,
        )
        assert result is not None
        assert result.source == "texte (analyse rapide)"
        assert len(result.employees) == 1
        emp = result.employees[0]
        assert emp.employee_id == "e1"
        assert all(d.heures == 8 and d.nature == "reel" for d in emp.days)
        assert len(emp.days) > 0

    def test_numeric_day_range(self):
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="Sophie Durand 7h du 2 au 5",
            roster=ROSTER,
        )
        assert result is not None
        assert result.employees[0].employee_id == "e2"
        assert [d.jour for d in result.employees[0].days] == [2, 3, 4, 5]

    def test_prevu_nature_detected(self):
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="Paul Martin est prévu 8h le 10",
            roster=ROSTER,
        )
        assert result is not None
        assert result.employees[0].days[0].nature == "prevu"

    def test_returns_none_when_ambiguous_employees(self):
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="8h du lundi au vendredi pour tout le monde",
            roster=ROSTER,
        )
        assert result is None

    def test_returns_none_without_hours(self):
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="Paul Martin en congé toute la semaine",
            roster=ROSTER,
        )
        assert result is None
