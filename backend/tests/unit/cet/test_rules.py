"""Tests règles CET."""

from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cet_balance_hours,
    compute_spareable_overtime_hours,
    validate_deposit_hours,
    validate_withdraw_hours,
)


def test_balance_deposits_minus_withdrawals():
    movements = [
        CetMovementRow("deposit_hs", 10, "validated"),
        CetMovementRow("withdraw_rest", 3, "validated"),
        CetMovementRow("deposit_hs", 2, "pending"),
    ]
    assert compute_cet_balance_hours(movements) == 7.0


def test_balance_includes_deposit_cp():
    movements = [
        CetMovementRow("deposit_cp", 0, "validated", days=2, year=2026),
    ]
    assert compute_cet_balance_hours(movements, hours_per_rest_day=7) == 14.0


def test_spareable_overtime_excludes_committed_deposits():
    movements = [
        CetMovementRow("deposit_hs", 4, "pending"),
        CetMovementRow("deposit_hs", 2, "validated"),
    ]
    assert compute_spareable_overtime_hours(10, movements) == 4.0


def test_validate_deposit_rejects_over_limit():
    try:
        validate_deposit_hours(5, 3)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "insuffisantes" in str(e)


def test_validate_withdraw_rejects_over_balance():
    try:
        validate_withdraw_hours(8, 5)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "insuffisant" in str(e)
