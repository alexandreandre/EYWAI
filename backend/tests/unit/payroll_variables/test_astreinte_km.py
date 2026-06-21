"""Tests domaine — éligibilité indemnité km astreinte."""

from __future__ import annotations

from datetime import date

import pytest

from app.modules.payroll_variables.domain.astreinte_km import (
    astreinte_week_mondays,
    evaluate_astreinte_weekend_km,
    is_eligible_astreinte_km,
    qualifying_week_mondays,
    resolve_astreinte_km_quantity,
    weekend_work_days,
)
from tests.unit.payroll.fixtures.baremes_km_excel import baremes_km_excel_fixture


def test_weekend_work_days_detects_saturday():
    cal = [{"jour": 7, "heures_faites": 4.0}]
    days = weekend_work_days(cal, 2026, 3, [5, 6])
    assert len(days) == 1
    assert days[0]["jour"] == 7


def test_astreinte_week_mondays():
    mondays = astreinte_week_mondays([date(2026, 3, 7)])
    assert date(2026, 3, 2) in mondays


def test_same_iso_week_requires_overlap():
    astreinte = {date(2026, 3, 2)}
    weekend = [{"jour": 7, "heures_faites": 3}]
    q = qualifying_week_mondays(
        astreinte, weekend, 2026, 3, "same_iso_week"
    )
    assert date(2026, 3, 2) in q

    weekend_other = [{"jour": 21, "heures_faites": 3}]
    q2 = qualifying_week_mondays(
        astreinte, weekend_other, 2026, 3, "same_iso_week"
    )
    assert len(q2) == 0


def test_month_overlap_eligible_without_same_week():
    conditions = {"astreinte_link_mode": "month_overlap"}
    assert is_eligible_astreinte_km(
        conditions,
        astreinte_mondays={date(2026, 3, 2)},
        weekend_days=[{"jour": 21, "heures_faites": 2}],
        year=2026,
        month=3,
    )


def test_resolve_quantity_once_if_eligible():
    qty = resolve_astreinte_km_quantity(
        {"quantity_mode": "once_if_eligible"},
        qualifying_weeks={date(2026, 3, 2)},
        weekend_days=[{"jour": 7}],
    )
    assert qty == 1.0


def test_evaluate_full_flow_joubert():
    rule = {
        "conditions": {
            "astreinte_link_mode": "same_iso_week",
            "quantity_mode": "once_if_eligible",
        }
    }
    emp = {
        "specificites_paie": {
            "deplacement_astreinte": {
                "enabled": True,
                "distance_km_one_way": 22.2,
                "vehicle_cv": 7,
                "vehicle_type": "voitures",
            }
        }
    }
    result = evaluate_astreinte_weekend_km(
        rule,
        emp,
        year=2026,
        month=3,
        calendrier_reel=[{"jour": 7, "heures_faites": 4}],
        astreinte_shift_dates=[date(2026, 3, 6)],
        baremes_km=baremes_km_excel_fixture(),
    )
    assert result["eligible"] is True
    assert result["amount"] == pytest.approx(17.01, abs=0.01)


def test_evaluate_skip_no_weekend():
    rule = {"conditions": {}}
    emp = {
        "specificites_paie": {
            "deplacement_astreinte": {
                "enabled": True,
                "distance_km_one_way": 22.2,
                "vehicle_cv": 7,
            }
        }
    }
    result = evaluate_astreinte_weekend_km(
        rule,
        emp,
        year=2026,
        month=3,
        calendrier_reel=[],
        astreinte_shift_dates=[date(2026, 3, 6)],
        baremes_km=baremes_km_excel_fixture(),
    )
    assert result["amount"] == 0
    assert result["details"]["skip_reason"] == "no_weekend_work"
