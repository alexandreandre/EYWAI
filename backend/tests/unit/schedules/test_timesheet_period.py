"""Tests unitaires de la détection de période des relevés de pointeuse."""

from datetime import date

import pytest

from app.modules.schedules.application.timesheet_period import (
    detect_timesheet_period,
    format_period_context,
    format_week_anchor_context,
    resolve_effective_target_month,
    suggested_target_month,
)
from tests.fixtures.timesheets.ocr_samples import (
    CROSS_MONTH,
    MONTHLY_PARTIAL,
    WEEKDAYS_ONLY,
    WEEKLY_HEADER,
    WEEK_NUMBER_ONLY,
)


class TestDetectWeeklyHeader:
    def test_semaine_du_au(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=6
        )
        assert det.scope == "weekly"
        assert det.confidence == "high"
        assert det.start_date == date(2025, 6, 3)
        assert det.end_date == date(2025, 6, 9)
        assert len(det.detected_dates) >= 5

    def test_no_period_warning_when_in_target_month(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=6
        )
        assert not any("hors du mois" in w for w in det.warnings)


class TestDetectMonthly:
    def test_many_dates_span(self):
        det = detect_timesheet_period(
            MONTHLY_PARTIAL, target_year=2025, target_month=6
        )
        assert det.scope == "monthly"
        assert det.start_date == date(2025, 6, 1)
        assert det.end_date == date(2025, 6, 30)


class TestDetectUnknown:
    def test_weekdays_only_low_confidence(self):
        det = detect_timesheet_period(
            WEEKDAYS_ONLY, target_year=2025, target_month=6
        )
        assert det.scope == "unknown"
        assert det.confidence == "low"
        assert any("Aucune date explicite" in w for w in det.warnings)

    def test_week_number_only(self):
        det = detect_timesheet_period(
            WEEK_NUMBER_ONLY, target_year=2025, target_month=6
        )
        assert det.scope == "weekly"
        assert det.confidence == "low"
        assert any("Numéro de semaine" in w for w in det.warnings)


class TestCrossMonth:
    def test_warns_cross_month(self):
        det = detect_timesheet_period(
            CROSS_MONTH, target_year=2025, target_month=6
        )
        assert any("cheval sur deux mois" in w for w in det.warnings)

    def test_outside_target_month_before_correction(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=5
        )
        assert any("hors du mois" in w for w in det.warnings)


class TestResolveEffectiveTargetMonth:
    def test_auto_corrects_when_entirely_in_other_month(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=5
        )
        y, m, corrected, msg = resolve_effective_target_month(det, 2025, 5)
        assert corrected is True
        assert (y, m) == (2025, 6)
        assert msg is not None
        assert "juin 2025" in msg

    def test_no_correction_when_already_in_target_month(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=6
        )
        y, m, corrected, _msg = resolve_effective_target_month(det, 2025, 6)
        assert corrected is False
        assert (y, m) == (2025, 6)

    def test_no_correction_for_cross_month_period(self):
        det = detect_timesheet_period(
            CROSS_MONTH, target_year=2025, target_month=6
        )
        _y, _m, corrected, _msg = resolve_effective_target_month(det, 2025, 6)
        assert corrected is False


class TestDocumentScopeOverride:
    def test_force_weekly(self):
        det = detect_timesheet_period(
            WEEKDAYS_ONLY,
            target_year=2025,
            target_month=6,
            document_scope="weekly",
        )
        assert det.scope == "weekly"


class TestFormatContext:
    def test_period_context_includes_target_days(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=6
        )
        ctx = format_period_context(det, 2025, 6)
        assert "jours 3" in ctx or "jours 3," in ctx or "3, 4" in ctx

    def test_week_anchor_maps_days(self):
        ctx = format_week_anchor_context(date(2025, 6, 2), 2025, 6)
        assert "lundi → jour 2" in ctx
        assert "mardi → jour 3" in ctx


class TestSuggestedTargetMonth:
    def test_returns_start_month(self):
        det = detect_timesheet_period(
            WEEKLY_HEADER, target_year=2025, target_month=5
        )
        assert suggested_target_month(det) == (2025, 6)

    def test_none_when_no_dates(self):
        det = detect_timesheet_period(
            WEEKDAYS_ONLY, target_year=2025, target_month=6
        )
        assert suggested_target_month(det) is None
