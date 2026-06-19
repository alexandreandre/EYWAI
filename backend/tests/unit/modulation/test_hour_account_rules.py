"""Tests compte d'heures modulation — règles domaine."""

from app.modules.modulation.domain.hour_account_rules import (
    can_debit_recovery,
    compute_acquired_and_taken,
    compute_balance_from_movements,
    reduce_payroll_hs_events,
    split_hs_for_period,
    sum_hs_from_payroll_events,
)


def test_split_hs_franchise_14_of_20():
    r = split_hs_for_period(20.0, 14.0, 0.0, 0.0)
    assert r.to_account == 14.0
    assert r.to_pay == 6.0


def test_split_hs_all_to_account_under_franchise():
    r = split_hs_for_period(10.0, 14.0, 0.0, 0.0)
    assert r.to_account == 10.0
    assert r.to_pay == 0.0


def test_split_hs_franchise_partially_consumed():
    r = split_hs_for_period(10.0, 14.0, 10.0, 5.0)
    assert r.to_account == 4.0
    assert r.to_pay == 6.0


def test_split_hs_max_balance_caps_account():
    r = split_hs_for_period(20.0, 14.0, 0.0, 12.0, max_balance=14.0)
    assert r.to_account == 2.0
    assert r.to_pay == 18.0


def test_balance_from_movements():
    movements = [
        {"movement_type": "credit_hs", "hours": 14, "status": "applied_payroll"},
        {"movement_type": "debit_recovery", "hours": 4, "status": "validated"},
        {"movement_type": "credit_hs", "hours": 5, "status": "pending"},
    ]
    assert compute_balance_from_movements(movements) == 10.0


def test_acquired_and_taken():
    movements = [
        {"movement_type": "opening_balance", "hours": 8, "status": "validated"},
        {"movement_type": "credit_hs", "hours": 6, "status": "applied_payroll"},
        {"movement_type": "debit_recovery", "hours": 3, "status": "validated"},
    ]
    acquired, taken = compute_acquired_and_taken(movements)
    assert acquired == 14.0
    assert taken == 3.0


def test_can_debit_recovery():
    assert can_debit_recovery(10.0, 8.0)
    assert not can_debit_recovery(5.0, 8.0)


def test_sum_hs_from_events():
    events = [
        {"type": "travail_hs25", "heures": 5},
        {"type": "travail_hs50", "heures": 3},
        {"type": "travail_base", "heures": 35},
    ]
    assert sum_hs_from_payroll_events(events) == 8.0


def test_reduce_payroll_hs_events():
    events = [
        {"type": "travail_hs25", "heures": 10, "jour": 5},
        {"type": "travail_hs50", "heures": 4, "jour": 6},
    ]
    reduced, deferred = reduce_payroll_hs_events(events, 12.0)
    assert deferred == 12.0
    total_remaining = sum(
        e.get("heures", 0) for e in reduced if str(e.get("type", "")).startswith("travail_hs")
    )
    assert total_remaining == 2.0
