"""Tests unitaires — verrouillage édition manuelle des bulletins."""

from datetime import date

import pytest

from app.modules.payslips.domain.period_edit_lock import (
    DEFAULT_CUTOFF_DAY,
    is_payslip_manual_edit_allowed,
    lock_start_date,
    manual_edit_allowed_until,
    normalize_cutoff_day,
    payslip_manual_edit_block_reason,
)


def test_lock_start_date_june_to_july():
    assert lock_start_date(2026, 6, 15) == date(2026, 7, 15)


def test_lock_start_date_december_to_january():
    assert lock_start_date(2026, 12, 15) == date(2027, 1, 15)


def test_manual_edit_allowed_until_june():
    assert manual_edit_allowed_until(2026, 6, 15) == date(2026, 7, 14)


def test_is_allowed_before_cutoff():
    assert is_payslip_manual_edit_allowed(
        2026, 6, cutoff_day=15, today=date(2026, 7, 14)
    )


def test_is_blocked_from_cutoff():
    assert not is_payslip_manual_edit_allowed(
        2026, 6, cutoff_day=15, today=date(2026, 7, 15)
    )


def test_block_reason_when_locked():
    reason = payslip_manual_edit_block_reason(
        2026, 6, cutoff_day=15, today=date(2026, 7, 15)
    )
    assert reason is not None
    assert "juin 2026" in reason
    assert "15 juillet 2026" in reason


def test_block_reason_none_when_open():
    assert (
        payslip_manual_edit_block_reason(
            2026, 6, cutoff_day=15, today=date(2026, 7, 14)
        )
        is None
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, DEFAULT_CUTOFF_DAY), (0, 1), (15, 15), (31, 28), ("20", 20)],
)
def test_normalize_cutoff_day(raw, expected):
    assert normalize_cutoff_day(raw) == expected
