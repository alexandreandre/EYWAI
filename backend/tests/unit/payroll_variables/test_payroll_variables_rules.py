"""Tests variables paie — règles domaine."""

from app.modules.payroll_variables.domain.rules import (
    compute_rule_amount,
    employee_matches_conditions,
)


def test_fixed_monthly_productivity_36():
    amount = compute_rule_amount("fixed_monthly", 36.0, None, 1.0)
    assert amount == 36.0


def test_astreinte_two_weeks():
    amount = compute_rule_amount("per_astreinte_week", 50.0, None, 2.0)
    assert amount == 100.0


def test_modulation_payout_below_threshold():
    amount = compute_rule_amount(
        "per_modulation_payout",
        15.0,
        None,
        2.0,
        conditions={"min_balance_hours": 5},
    )
    assert amount == 0.0


def test_modulation_payout_above_threshold():
    amount = compute_rule_amount(
        "per_modulation_payout",
        15.0,
        None,
        8.0,
        conditions={"min_balance_hours": 5},
    )
    assert amount == 120.0


def test_employee_statut_filter():
    emp = {"statut": "Cadre"}
    assert employee_matches_conditions(emp, {"statuts": ["Cadre"]})
    assert not employee_matches_conditions(emp, {"statuts": ["Non-Cadre"]})
