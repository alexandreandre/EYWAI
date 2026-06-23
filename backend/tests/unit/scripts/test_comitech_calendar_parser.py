"""Tests parseur calendrier Excel Comitech Composite."""

from datetime import date

from scripts.comitech_calendar_parser import (
    classify_planned_day,
    parse_employee_sheet,
)


def test_classify_weekday_travail():
    entry = classify_planned_day(date(2026, 3, 4), None, None)
    assert entry["type"] == "travail"
    assert entry["heures_prevues"] == 7.8


def test_classify_weekend():
    entry = classify_planned_day(date(2026, 3, 7), None, None)
    assert entry["type"] == "weekend"
    assert entry["heures_prevues"] == 0.0


def test_classify_cp_day():
    entry = classify_planned_day(date(2026, 2, 2), None, 1)
    assert entry["type"] == "conge"
    assert entry["heures_prevues"] == 7.8


def test_classify_public_holiday():
    entry = classify_planned_day(date(2026, 5, 1), "Fete du W", None)
    assert entry["type"] == "ferie"
    assert entry["heures_prevues"] is None


def test_classify_half_cp():
    entry = classify_planned_day(date(2026, 6, 15), None, 0.5)
    assert entry["type"] == "conge"
    assert entry["heures_prevues"] == 3.9


def test_classify_blank_marker_pont():
    entry = classify_planned_day(date(2026, 3, 27), " ", None)
    assert entry["type"] == "conge"
    assert entry["heures_prevues"] == 7.8


def test_parse_employee_sheet_has_twelve_months():
    import openpyxl
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts/data/calendrier_2026_comitech.xlsx"
    if not path.is_file():
        return
    wb = openpyxl.load_workbook(path, data_only=True)
    parsed = parse_employee_sheet(wb["BOUFRIDA"])
    assert len(parsed) == 12
    assert len(parsed[1]) >= 28
