"""Tests de l'analyse déterministe rapide (sans LLM) du remplissage calendrier."""

from app.modules.schedules.application.nl_fast_path import (
    is_mirror_planning_instruction,
    try_fast_parse_instruction,
    try_mirror_planned_instruction,
)
from app.modules.schedules.schemas.ai import RosterEmployee

ROSTER = [
    RosterEmployee(id="e1", first_name="Paul", last_name="Martin"),
    RosterEmployee(id="e2", first_name="Sophie", last_name="Durand"),
]

BUGNY_ROSTER = ROSTER + [
    RosterEmployee(id="e-bugny", first_name="Michel", last_name="BUGNY"),
]

PLANNED_MAY = [
    {"jour": 2, "type": "travail", "heures_prevues": 7.0},
    {"jour": 3, "type": "travail", "heures_prevues": 7.0},
    {"jour": 5, "type": "conge", "heures_prevues": 0},
]


def _load_planned(_employee_id: str, _year: int, _month: int):
    return PLANNED_MAY


class TestMirrorPlanningInstruction:
    def test_detects_exactly_as_planned_phrase(self):
        assert is_mirror_planning_instruction(
            "Michel Bugny a fait exactement toutes les heures qui lui étaient prévues"
        )

    def test_mirror_planned_hours_for_named_employee(self):
        result = try_mirror_planned_instruction(
            year=2026,
            month=5,
            instruction=(
                "En mai, Michel Bugny a fait exactement toutes les heures "
                "qui lui étaient prévues, pas +, pas moins"
            ),
            roster=BUGNY_ROSTER,
            load_planned=_load_planned,
        )
        assert result is not None
        assert result.source == "texte (reprise planning)"
        assert len(result.employees) == 1
        emp = result.employees[0]
        assert emp.employee_id == "e-bugny"
        assert [d.jour for d in emp.days] == [2, 3, 5]
        assert all(d.nature == "reel" for d in emp.days)
        assert emp.days[0].heures == 7.0
        assert emp.days[2].type == "conge"

    def test_mirror_single_employee_without_name(self):
        result = try_mirror_planned_instruction(
            year=2026,
            month=5,
            instruction="a fait exactement comme prévu, pas plus pas moins",
            roster=[BUGNY_ROSTER[2]],
            target=BUGNY_ROSTER[2],
            load_planned=_load_planned,
        )
        assert result is not None
        assert result.employees[0].employee_id == "e-bugny"
        assert len(result.employees[0].days) == 3

    def test_mirror_broadcast_all_employees(self):
        result = try_mirror_planned_instruction(
            year=2026,
            month=5,
            instruction="tout le monde a fait exactement comme prévu",
            roster=BUGNY_ROSTER,
            force_broadcast=True,
            load_planned=_load_planned,
        )
        assert result is not None
        assert len(result.employees) == 3
        assert all(len(emp.days) == 3 for emp in result.employees)

    def test_mirror_returns_none_without_mirror_hint(self):
        result = try_mirror_planned_instruction(
            year=2026,
            month=5,
            instruction="Paul Martin a fait 8h du lundi au jeudi",
            roster=ROSTER,
            load_planned=_load_planned,
        )
        assert result is None


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
        assert result is not None
        assert len(result.employees) == 2

    def test_broadcast_zero_hours_with_exclusion(self):
        roster = ROSTER + [
            RosterEmployee(id="e3", first_name="Fredo", last_name="André"),
        ]
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="Met 0h faites à tout le monde sauf fredo andré",
            roster=roster,
        )
        assert result is not None
        assert result.source == "texte (analyse rapide)"
        assert len(result.employees) == 2
        assert all(emp.employee_id in ("e1", "e2") for emp in result.employees)
        assert all(
            all(d.heures == 0 and d.nature == "reel" for d in emp.days)
            for emp in result.employees
        )
        assert len(result.employees[0].days) == 30

    def test_returns_none_without_hours(self):
        result = try_fast_parse_instruction(
            year=2026,
            month=6,
            instruction="Paul Martin en congé toute la semaine",
            roster=ROSTER,
        )
        assert result is None
