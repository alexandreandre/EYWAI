"""Tests règles comptabilisation pointages."""

from app.modules.schedules.domain.punch_accounting_entities import (
    PlannedShiftBreak,
    PunchAccountingSettings,
    PunchShiftSlot,
    THREE_DAILY_SLOTS_PRESET,
)
from app.modules.schedules.domain.punch_accounting_rules import (
    compute_from_raw_times,
    parse_hhmm_value,
    slot_from_row,
)


def _default_slots() -> list[PunchShiftSlot]:
    return [slot_from_row({**row, "id": f"slot-{i}"}) for i, row in enumerate(THREE_DAILY_SLOTS_PRESET)]


class TestParseHhmm:
    def test_integer_format(self):
        assert parse_hhmm_value(800) == 8 * 60
        assert parse_hhmm_value(1548) == 15 * 60 + 48
        assert parse_hhmm_value(445) == 4 * 60 + 45

    def test_zero_is_none(self):
        assert parse_hhmm_value(0) is None


class TestLewisSampleRows:
    """Recette Elsa — échantillon juin 2026."""

    def setup_method(self):
        self.settings = PunchAccountingSettings(
            enabled=True,
            tolerance_minutes=30,
            default_break_deduct_minutes=45,
            slot_detection="shift_code",
        )
        self.slots = _default_slots()

    def test_francine_normal_day(self):
        result = compute_from_raw_times(
            entry_raw=800,
            exit_raw=1548,
            shift_code="A",
            settings=self.settings,
            slots=self.slots,
        )
        assert result.pointed_net_hours == 7.05
        assert result.theoretical_net_hours == 7.0
        assert result.overtime_hours == 0.0
        assert not result.needs_review

    def test_bruno_overtime_late_exit(self):
        result = compute_from_raw_times(
            entry_raw=740,
            exit_raw=1630,
            shift_code="A",
            settings=self.settings,
            slots=self.slots,
        )
        assert result.pointed_net_hours == 8.08
        assert result.needs_review
        assert result.overtime_hours > 0
        assert result.overtime_reason in ("late_exit", "daily_excess")

    def test_maria_code_b_morning(self):
        result = compute_from_raw_times(
            entry_raw=438,
            exit_raw=1200,
            shift_code="B",
            settings=self.settings,
            slots=self.slots,
        )
        assert result.pointed_net_hours == 6.62
        assert abs(result.theoretical_net_hours - 6.5) < 0.01

    def test_gregory_large_overtime(self):
        result = compute_from_raw_times(
            entry_raw=728,
            exit_raw=1754,
            shift_code="A",
            settings=self.settings,
            slots=self.slots,
        )
        assert result.pointed_net_hours == 9.68
        assert result.needs_review

    def test_absent_day(self):
        result = compute_from_raw_times(
            entry_raw=800,
            exit_raw=0,
            shift_code="A",
            settings=self.settings,
            slots=self.slots,
        )
        assert result.is_absent
        assert result.accounted_hours == 0.0

    def test_herve_equipe_paid_lunch_via_planning(self):
        """Pause déjeuner payée : 30 min planifiées → déduction 15 min seulement."""
        settings = PunchAccountingSettings(
            enabled=True,
            tolerance_minutes=30,
            slot_detection="nearest_entry",
        )
        result = compute_from_raw_times(
            entry_raw=437,
            exit_raw=1200,
            shift_code="A",
            settings=settings,
            slots=self.slots,
            planned_shift=PlannedShiftBreak(paid_break_minutes=30),
        )
        assert abs(result.pointed_net_hours - 7.13) < 0.02
