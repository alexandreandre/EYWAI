"""Tests prime présence hebdomadaire."""

from datetime import date

from app.modules.payroll_variables.domain.presence_week import (
    absence_days_from_requests,
    evaluate_presence_weeks,
    iso_week_mondays_in_month,
    week_has_disqualifying_absence,
)


def test_iso_week_mondays_june_2026():
    mondays = iso_week_mondays_in_month(2026, 6)
    assert len(mondays) >= 4
    assert all(m.weekday() == 0 for m in mondays)


def test_absence_disqualifies_week():
    monday = date(2026, 6, 1)
    days = {date(2026, 6, 3)}
    assert week_has_disqualifying_absence(monday, days)
    assert not week_has_disqualifying_absence(monday, set())


def test_evaluate_zero_when_types_not_configured():
    result = evaluate_presence_weeks(
        year=2026,
        month=6,
        absence_requests=[],
        conditions={"amount_per_week": 6.0, "absence_types": []},
    )
    assert result["quantity"] == 0.0


def test_evaluate_eligible_weeks_without_absence():
    requests = [
        {
            "type": "conge_paye",
            "status": "validated",
            "selected_days": ["2026-06-10"],
        }
    ]
    result = evaluate_presence_weeks(
        year=2026,
        month=6,
        absence_requests=requests,
        conditions={
            "amount_per_week": 6.0,
            "absence_types": ["conge_paye"],
        },
    )
    assert result["quantity"] < len(iso_week_mondays_in_month(2026, 6))


def test_evaluate_all_weeks_when_no_matching_absence():
    result = evaluate_presence_weeks(
        year=2026,
        month=6,
        absence_requests=[],
        conditions={
            "amount_per_week": 6.0,
            "absence_types": ["maladie"],
        },
    )
    assert result["quantity"] == float(len(iso_week_mondays_in_month(2026, 6)))


def test_absence_days_from_requests_filters_type():
    days = absence_days_from_requests(
        [
            {
                "type": "rtt",
                "status": "validated",
                "selected_days": ["2026-06-05"],
            },
            {
                "type": "conge_paye",
                "status": "validated",
                "selected_days": ["2026-06-06"],
            },
        ],
        absence_types=["conge_paye"],
    )
    assert days == {date(2026, 6, 6)}
