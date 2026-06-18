"""Tests règles CET — transferts CP."""

from app.modules.cet.domain.rules import (
    CetMovementRow,
    compute_cp_days_committed_for_absences,
    compute_cp_transferred_days_year,
    convert_cp_days_between_units,
    remaining_cp_transfer_quota,
    validate_deposit_cp,
)


def test_cp_transferred_includes_pending_and_validated():
    movements = [
        CetMovementRow("deposit_cp", 0, "pending", days=2, year=2026),
        CetMovementRow("deposit_cp", 0, "validated", days=3, year=2026),
        CetMovementRow("deposit_cp", 0, "rejected", days=5, year=2026),
        CetMovementRow("deposit_cp", 0, "validated", days=1, year=2025),
    ]
    assert compute_cp_transferred_days_year(movements, 2026) == 5.0


def test_remaining_quota_null_when_unlimited():
    assert remaining_cp_transfer_quota(None, 10) is None


def test_remaining_quota_respects_plafond():
    assert remaining_cp_transfer_quota(5, 3) == 2.0
    assert remaining_cp_transfer_quota(5, 6) == 0.0


def test_cp_committed_on_validation_includes_pending():
    movements = [
        CetMovementRow("deposit_cp", 0, "pending", days=2, year=2026),
        CetMovementRow("deposit_cp", 0, "validated", days=1, year=2026),
    ]
    assert (
        compute_cp_days_committed_for_absences(
            movements, 2026, cp_debit_timing="on_validation"
        )
        == 3.0
    )


def test_cp_committed_on_payroll_only_applied():
    movements = [
        CetMovementRow("deposit_cp", 0, "pending", days=2, year=2026),
        CetMovementRow("deposit_cp", 0, "validated", days=1, year=2026),
        CetMovementRow("deposit_cp", 0, "applied_payroll", days=4, year=2026),
    ]
    assert (
        compute_cp_days_committed_for_absences(
            movements, 2026, cp_debit_timing="on_payroll"
        )
        == 4.0
    )


def test_validate_deposit_cp_rejects_over_quota():
    try:
        validate_deposit_cp(3, quota_remaining=2, cp_balance_available=10)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "Plafond" in str(e)


def test_validate_deposit_cp_rejects_over_cp_balance():
    try:
        validate_deposit_cp(5, quota_remaining=None, cp_balance_available=3)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "insuffisant" in str(e)


def test_convert_ouvres_to_ouvrables():
    assert convert_cp_days_between_units(5, "ouvres", "ouvrables", 1.2) == 6.0


def test_convert_ouvrables_to_ouvres():
    assert convert_cp_days_between_units(6, "ouvrables", "ouvres", 1.2) == 5.0
