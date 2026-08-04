"""Tests règles comptabilisation pointages."""

from app.modules.schedules.domain.punch_accounting_entities import (
    INDUSTRIAL_3X8_BREAKS_PRESET,
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


class TestIndustrial3x8Breaks:
    """Recette MBC — poste 04h–12h, repas 30 min déduit, net 7,5 h."""

    def setup_method(self):
        self.settings = PunchAccountingSettings(
            enabled=True,
            tolerance_minutes=30,
            slot_detection="shift_code",
        )
        self.slots = [
            slot_from_row({**row, "id": f"mbc-{i}"})
            for i, row in enumerate(INDUSTRIAL_3X8_BREAKS_PRESET)
        ]

    def test_matin_shift_7_5_net(self):
        result = compute_from_raw_times(
            entry_raw=400,
            exit_raw=1200,
            shift_code="MATIN",
            settings=self.settings,
            slots=self.slots,
        )
        assert result.pointed_net_hours == 7.5
        assert result.theoretical_net_hours == 7.5

    def test_unpaid_from_calendar_overrides_slot(self):
        result = compute_from_raw_times(
            entry_raw=400,
            exit_raw=1200,
            shift_code="MATIN",
            settings=self.settings,
            slots=self.slots,
            planned_shift=PlannedShiftBreak(unpaid_break_minutes=30),
        )
        assert result.pointed_net_hours == 7.5


class TestBadgeuseMinutesSinceMidnight:
    """Badgeuse fournit des minutes depuis minuit (240 = 04:00), pas du HHMM entier."""

    def test_badgeuse_service_matin_7_5(self, monkeypatch):
        from app.modules.schedules.application import punch_accounting_service as svc
        from app.modules.schedules.domain.punch_accounting_entities import (
            INDUSTRIAL_3X8_BREAKS_PRESET,
            PunchAccountingSettings,
        )
        from app.modules.schedules.domain.punch_accounting_rules import slot_from_row

        settings = PunchAccountingSettings(enabled=True, tolerance_minutes=30)
        slots = [
            slot_from_row({**row, "id": f"mbc-{i}"})
            for i, row in enumerate(INDUSTRIAL_3X8_BREAKS_PRESET)
        ]
        monkeypatch.setattr(svc.repo, "get_settings", lambda _c: settings)
        monkeypatch.setattr(svc.repo, "list_slots", lambda _c: slots)

        heures, needs_review, overtime, _ = svc.compute_accounted_hours_for_badgeuse_day(
            "company-1",
            entry_minutes=240,
            exit_minutes=720,
            shift_code="MATIN",
            planned_unpaid_break_minutes=30,
        )
        assert heures == 7.5
        assert not needs_review
        assert overtime == 0.0


class TestBreakThreshold:
    """Seuil de présence en deçà duquel aucune pause n'est déduite.

    Cas Colorplast : 30 min de pause déjeuner, mais rien sur une demi-journée.
    Journées relevées sur leurs feuilles de pointage papier.
    """

    def _settings(self, threshold: int) -> PunchAccountingSettings:
        return PunchAccountingSettings(
            enabled=True,
            tolerance_minutes=30,
            default_break_deduct_minutes=30,
            break_threshold_minutes=threshold,
            slot_detection="shift_code",
        )

    def _hours(self, entry_raw: int, exit_raw: int, threshold: int) -> float:
        result = compute_from_raw_times(
            entry_raw=entry_raw,
            exit_raw=exit_raw,
            shift_code=None,
            settings=self._settings(threshold),
            slots=[],
        )
        return result.accounted_hours

    def test_journee_longue_subit_la_pause(self):
        # 6h00 → 15h00 = 9 h brutes, 8,5 h retenues sur la feuille
        assert self._hours(600, 1500, 360) == 8.5

    def test_demi_journee_sous_le_seuil_ne_subit_rien(self):
        # 6h00 → 12h00 = 6 h pile, comptées 6 h sur la feuille
        assert self._hours(600, 1200, 360) == 6.0

    def test_vendredi_court_ne_subit_rien(self):
        # 7h00 → 12h00 = 5 h, comptées 5 h sur la feuille
        assert self._hours(700, 1200, 360) == 5.0

    def test_juste_au_dessus_du_seuil_subit_la_pause(self):
        # 6h00 → 12h01 : une minute de plus, la pause s'applique
        assert self._hours(600, 1201, 360) == 5.52

    def test_seuil_a_zero_ne_change_rien(self):
        # Non-régression : sans seuil, la pause s'applique à toute journée
        assert self._hours(600, 1200, 0) == 5.5
        assert self._hours(600, 1500, 0) == 8.5
