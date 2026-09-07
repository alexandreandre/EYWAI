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


class TestVerrouDesactivable:
    """enabled=false dans la config globale = verrou coupé (phase de recette)."""

    def test_assert_ne_leve_plus_quand_desactive(self):
        from datetime import date as _d

        from app.modules.payslips.application.period_edit_lock import (
            assert_payslip_manual_edit_allowed,
        )

        # Période archi-verrouillée (juillet 2026 lu en septembre) : passe.
        assert_payslip_manual_edit_allowed(
            {"year": 2026, "month": 7},
            cutoff_day=15,
            lock_enabled=False,
            today=_d(2026, 9, 7),
        )

    def test_assert_leve_toujours_quand_active(self):
        from datetime import date as _d

        import pytest as _pytest

        from app.modules.payslips.application.period_edit_lock import (
            assert_payslip_manual_edit_allowed,
        )

        with _pytest.raises(ValueError, match="verrouillée"):
            assert_payslip_manual_edit_allowed(
                {"year": 2026, "month": 7},
                cutoff_day=15,
                lock_enabled=True,
                today=_d(2026, 9, 7),
            )

    def test_enrich_marque_deverrouille_quand_desactive(self):
        from datetime import date as _d

        from app.modules.payslips.application.period_edit_lock import (
            enrich_payslip_detail_with_edit_lock,
        )

        out = enrich_payslip_detail_with_edit_lock(
            {"year": 2026, "month": 7},
            cutoff_day=15,
            lock_enabled=False,
            today=_d(2026, 9, 7),
        )
        assert out["period_edit_locked"] is False
        assert out["manual_edit_locked"] is False
        assert out["manual_edit_lock_reason"] is None

    def test_coercition_enabled_seul_false_booleen_desactive(self):
        from app.modules.payslips.infrastructure.payslip_edit_lock_config import (
            _coerce_enabled,
        )

        assert _coerce_enabled(False) is False
        assert _coerce_enabled(True) is True
        assert _coerce_enabled("false") is True  # chaîne ≠ booléen : verrou gardé
        assert _coerce_enabled(None) is True
