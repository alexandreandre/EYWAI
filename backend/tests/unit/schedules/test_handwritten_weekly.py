"""Tests feuilles hebdomadaires manuscrites DEBUT/FIN."""

from app.modules.schedules.application.employee_match import is_junk_employee_name
from app.modules.schedules.application.handwritten_weekly import (
    FORMAT_HINT,
    calculate_hours_from_range,
    weekday_to_month_day,
)
from app.modules.schedules.application.timesheet_page_consensus import (
    build_page_consensus,
)
from app.modules.schedules.application.timesheet_page_merge import merge_page_results


def _employee(name: str, week_number: int = 18) -> dict:
    return {
        "raw_name": name,
        "matricule": None,
        "week_number": week_number,
        "weekly_total_pdf": None,
        "days": [
            {
                "weekday": "lundi",
                "debut": "08:00",
                "fin": "17:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "mardi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "mercredi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
            {
                "weekday": "jeudi",
                "debut": "07:00",
                "fin": "16:00",
                "heures": None,
                "type": "travail",
            },
        ],
    }


def test_s18_weekday_maps_to_may_2026():
    assert (
        weekday_to_month_day(year=2026, month=5, week_number=18, weekday="lundi") == 4
    )
    assert (
        weekday_to_month_day(year=2026, month=5, week_number=18, weekday="vendredi")
        == 8
    )


def test_handwritten_range_hours_deducts_lunch_break():
    assert calculate_hours_from_range("8h", "17h") == 8.0
    assert calculate_hours_from_range("6h45", "16h") == 8.25
    assert calculate_hours_from_range("6h", "18h30") == 11.5


def test_hugo_not_junk_for_handwritten_format():
    assert is_junk_employee_name("HUGO")
    assert not is_junk_employee_name("HUGO", format_hint=FORMAT_HINT)


def test_consensus_and_merge_keep_six_handwritten_employees():
    payload = {
        "employees": [
            _employee("HUGO"),
            _employee("MICHEL"),
            _employee("ANTHONY"),
            _employee("LEO"),
            _employee("AURELIEN"),
            _employee("MARION"),
        ],
        "page_period_hint": "S18",
        "confidence": 0.86,
        "warnings": [],
    }

    page = build_page_consensus(
        page_index=1,
        vision_data=payload,
        text_data=None,
        year=2026,
        month=5,
    )
    merged = merge_page_results([page])

    assert [emp.raw_name for emp in merged.employees] == [
        "HUGO",
        "MICHEL",
        "ANTHONY",
        "LEO",
        "AURELIEN",
        "MARION",
    ]
    assert all(len(emp.days) == 4 for emp in merged.employees)
    assert all(emp.days[0]["jour"] == 4 for emp in merged.employees)
