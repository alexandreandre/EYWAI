"""Tests parseur calendrier prévu Excel Quadra."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.schedules.application.employee_match import (
    resolve_employee_for_planning_sheet,
)
from app.modules.schedules.application.planning_import.quadra_calendar import (
    classify_planned_day,
    is_quadra_planning_workbook,
    parse_quadra_planning_workbook,
)
from app.modules.schedules.application.timesheet_import.tabular_period import (
    ImportPeriodConfig,
)
from app.modules.schedules.schemas.ai import RosterEmployee

XLSX = Path(
    "/Users/alex/Desktop/Comitech Composite/Calendrier/calendrier 2026 comitech.xlsx"
)

ROSTER = [
    RosterEmployee(id="1", first_name="Samir", last_name="BOUFRIDA"),
    RosterEmployee(id="2", first_name="Michel", last_name="BOUVEYRON"),
    RosterEmployee(
        id="3",
        first_name="Vitor Manuel",
        last_name="CASANOVA DA SILVA",
    ),
    RosterEmployee(id="4", first_name="Lucas", last_name="CHAMBERT"),
]


@pytest.mark.skipif(not XLSX.is_file(), reason="Fichier calendrier Comitech absent")
def test_detect_quadra_workbook() -> None:
    content = XLSX.read_bytes()
    assert is_quadra_planning_workbook(content, XLSX.name)


@pytest.mark.skipif(not XLSX.is_file(), reason="Fichier calendrier Comitech absent")
def test_parse_quadra_year_mode() -> None:
    content = XLSX.read_bytes()
    parsed = parse_quadra_planning_workbook(
        content,
        XLSX.name,
        year=2026,
        period_config=ImportPeriodConfig(mode="year", year=2026, month=1),
        roster=ROSTER,
    )
    assert parsed.sheets_parsed >= 10
    assert len(parsed.month_groups) == 12
    first_group = parsed.month_groups[0]
    assert first_group["year"] == 2026
    assert first_group["month"] == 1
    employees = first_group["employees"]
    assert employees
    assert all(day["nature"] == "prevu" for emp in employees for day in emp["days"])


def test_resolve_sheet_last_name_only() -> None:
    match = resolve_employee_for_planning_sheet("BOUFRIDA", ROSTER)
    assert match.employee_id == "1"
    assert match.review_status == "ok"


def test_resolve_sheet_with_sommaire_hint_disambiguates() -> None:
    roster = [
        RosterEmployee(id="3", first_name="Vitor Manuel", last_name="CASANOVA DA SILVA"),
        RosterEmployee(id="5", first_name="Vitor Manuel", last_name="DA SILVA CARDOSO"),
        RosterEmployee(id="2", first_name="Michel", last_name="BOUVEYRON"),
    ]
    match = resolve_employee_for_planning_sheet(
        "CASANOVA",
        roster,
        hint_name="CASANOVA DA SILVA Vitor Manuel",
    )
    assert match.employee_id == "3"
    assert match.review_status in ("ok", "warning")

    match_b = resolve_employee_for_planning_sheet(
        "BOUVEYRON",
        roster,
        hint_name="BOUVEYRON Michel",
    )
    assert match_b.employee_id == "2"
    assert match_b.review_status in ("ok", "warning")


def test_classify_cp_day() -> None:
    from datetime import date

    entry = classify_planned_day(date(2026, 2, 3), None, 1.0)
    assert entry["type"] == "conge"
    assert entry["heures_prevues"] == pytest.approx(7.8)
