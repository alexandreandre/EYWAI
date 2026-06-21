"""Tests routage HS par politique entreprise."""

from app.modules.modulation.domain.hour_account_rules import route_hs_for_period


def test_route_pay_all():
    r = route_hs_for_period(10.0, "pay_all", 14, 0, 0)
    assert r.to_account == 0.0
    assert r.to_pay == 10.0


def test_route_account_all():
    r = route_hs_for_period(12.5, "account_all", 0, 0, 0, max_balance=5)
    assert r.to_account == 12.5
    assert r.to_pay == 0.0


def test_route_franchise_delegates():
    r = route_hs_for_period(20.0, "franchise", 14, 0, 0)
    assert r.to_account == 14.0
    assert r.to_pay == 6.0


def test_route_manual_valid():
    r = route_hs_for_period(
        8.0, "manual", 0, 0, 0, manual_to_account=5.0, manual_to_pay=3.0
    )
    assert r.to_account == 5.0
    assert r.to_pay == 3.0


def test_route_manual_invalid_falls_back_pay():
    r = route_hs_for_period(
        8.0, "manual", 0, 0, 0, manual_to_account=4.0, manual_to_pay=2.0
    )
    assert r.to_account == 0.0
    assert r.to_pay == 8.0
